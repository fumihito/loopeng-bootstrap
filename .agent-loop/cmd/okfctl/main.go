package main

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

const (
	version             = "0.3.0"
	maxReportOperations = 20
	maxConceptBytes     = 128 * 1024
)

var (
	conceptIDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9._/-]{0,239}$`)
	keyPattern       = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_-]*$`)
	dateHeading      = regexp.MustCompile(`^## [0-9]{4}-[0-9]{2}-[0-9]{2}$`)
	markdownLink     = regexp.MustCompile(`\[[^\]]+\]\(([^)]+)\)`)
	secretPatterns   = []*regexp.Regexp{
		regexp.MustCompile(`(?i)-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----`),
		regexp.MustCompile(`\bAKIA[0-9A-Z]{16}\b`),
		regexp.MustCompile(`\bASIA[0-9A-Z]{16}\b`),
		regexp.MustCompile(`\bgh[pousr]_[A-Za-z0-9]{24,}\b`),
		regexp.MustCompile(`\bsk-[A-Za-z0-9_-]{20,}\b`),
		regexp.MustCompile(`(?i)\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^\s]{8,}`),
		regexp.MustCompile(`(?i)authorization:\s*bearer\s+[A-Za-z0-9._~+/-]+=*`),
	}
)

type Frontmatter map[string]any

type Concept struct {
	ID          string      `json:"id"`
	Path        string      `json:"path"`
	Type        string      `json:"type"`
	Title       string      `json:"title"`
	Description string      `json:"description"`
	Status      string      `json:"status,omitempty"`
	Tags        []string    `json:"tags,omitempty"`
	Timestamp   string      `json:"timestamp,omitempty"`
	Frontmatter Frontmatter `json:"-"`
	Body        string      `json:"-"`
}

type Finding struct {
	Severity string `json:"severity"`
	Path     string `json:"path"`
	Message  string `json:"message"`
}

type ValidationReport struct {
	OK       bool      `json:"ok"`
	Root     string    `json:"root"`
	Version  string    `json:"validator_version"`
	Concepts int       `json:"concepts"`
	Errors   []Finding `json:"errors"`
	Warnings []Finding `json:"warnings"`
}

type MemoryOperation struct {
	Action     string `json:"action"`
	ProposalID string `json:"proposal_id"`
	ConceptID  string `json:"concept_id"`
	Document   string `json:"document"`
}

type MemoryReport struct {
	Role                 string            `json:"role"`
	Status               string            `json:"status"`
	ProcessedProposalIDs []string          `json:"processed_proposal_ids"`
	Operations           []MemoryOperation `json:"operations"`
	SkippedProposals     []any             `json:"skipped_proposals"`
	Conflicts            []any             `json:"conflicts"`
}

type ApplyResult struct {
	OK                 bool     `json:"ok"`
	Status             string   `json:"status"`
	AppliedConceptIDs  []string `json:"applied_concept_ids"`
	CreatedCount       int      `json:"created_count"`
	UpdatedCount       int      `json:"updated_count"`
	DeprecatedCount    int      `json:"deprecated_count"`
	ValidationWarnings int      `json:"validation_warning_count"`
	BackupPath         string   `json:"backup_path,omitempty"`
}

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	var err error
	switch os.Args[1] {
	case "version":
		fmt.Println(version)
		return
	case "init":
		err = cmdInit(os.Args[2:])
	case "validate":
		err = cmdValidate(os.Args[2:])
	case "reindex":
		err = cmdReindex(os.Args[2:])
	case "put":
		err = cmdPut(os.Args[2:])
	case "apply-report":
		err = cmdApplyReport(os.Args[2:])
	case "search":
		err = cmdSearch(os.Args[2:])
	case "match-brief-pattern":
		err = cmdMatchBriefPattern(os.Args[2:])
	case "show":
		err = cmdShow(os.Args[2:])
	case "stats":
		err = cmdStats(os.Args[2:])
	default:
		usage()
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "okfctl:", err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, `okfctl - deterministic OKF/LLMWiki utility

Commands:
  init          initialize an OKF v0.1 LLMWiki bundle
  validate      validate OKF conformance and the local LLMWiki profile
  reindex       regenerate progressive-disclosure index.md files
  put           atomically create or update one concept from stdin
  apply-report  transactionally apply a trusted memory-curator JSON report
  search        search concept metadata and bodies
  match-brief-pattern  rank active Loop Brief Pattern concepts by abstract match keys
  show          print a concept document by concept ID
  stats         print bundle counts by type and status
  version       print command version`)
}

func rootFlag(set *flag.FlagSet) *string {
	return set.String("root", "llmwiki", "OKF bundle root")
}

func canonicalRoot(value string) (string, error) {
	if value == "" {
		return "", errors.New("empty root")
	}
	abs, err := filepath.Abs(value)
	if err != nil {
		return "", err
	}
	info, err := os.Lstat(abs)
	if err == nil && info.Mode()&os.ModeSymlink != 0 {
		return "", fmt.Errorf("bundle root must not be a symlink: %s", abs)
	}
	return filepath.Clean(abs), nil
}

func cmdInit(args []string) error {
	set := flag.NewFlagSet("init", flag.ContinueOnError)
	rootArg := rootFlag(set)
	title := set.String("title", "Project LLMWiki", "bundle title")
	description := set.String("description", "Curated, version-controlled knowledge for coding agents.", "bundle description")
	if err := set.Parse(args); err != nil {
		return err
	}
	root, err := canonicalRoot(*rootArg)
	if err != nil {
		return err
	}
	dirs := []string{"concepts", "decisions", "constraints", "failure-patterns", "evaluation-rules", "recovery-patterns", "runbooks", "references", "loop-brief-patterns"}
	if err := os.MkdirAll(root, 0o755); err != nil {
		return err
	}
	for _, dir := range dirs {
		if err := os.MkdirAll(filepath.Join(root, dir), 0o755); err != nil {
			return err
		}
	}
	index := filepath.Join(root, "index.md")
	if _, err := os.Stat(index); errors.Is(err, os.ErrNotExist) {
		body := fmt.Sprintf("---\nokf_version: \"0.1\"\ntitle: %s\ndescription: %s\n---\n\n# %s\n\nThis bundle contains curated operational knowledge. Use the generated directory sections below for progressive disclosure.\n", yamlQuote(*title), yamlQuote(*description), *title)
		if err := atomicWrite(index, []byte(body), 0o644); err != nil {
			return err
		}
	}
	logPath := filepath.Join(root, "log.md")
	if _, err := os.Stat(logPath); errors.Is(err, os.ErrNotExist) {
		content := "# Directory Update Log\n\n## " + time.Now().UTC().Format("2006-01-02") + "\n* **Initialization**: Created the OKF LLMWiki bundle.\n"
		if err := atomicWrite(logPath, []byte(content), 0o644); err != nil {
			return err
		}
	}
	return reindex(root)
}

func cmdValidate(args []string) error {
	set := flag.NewFlagSet("validate", flag.ContinueOnError)
	rootArg := rootFlag(set)
	jsonOutput := set.Bool("json", false, "emit JSON")
	strict := set.Bool("strict", false, "treat profile warnings as errors")
	if err := set.Parse(args); err != nil {
		return err
	}
	root, err := canonicalRoot(*rootArg)
	if err != nil {
		return err
	}
	report := validateBundle(root)
	if *jsonOutput {
		encoded, _ := json.MarshalIndent(report, "", "  ")
		fmt.Println(string(encoded))
	} else {
		fmt.Printf("OKF bundle: %s\nConcepts: %d\n", report.Root, report.Concepts)
		for _, item := range report.Errors {
			fmt.Printf("ERROR %s: %s\n", item.Path, item.Message)
		}
		for _, item := range report.Warnings {
			fmt.Printf("WARN  %s: %s\n", item.Path, item.Message)
		}
		if report.OK && (!*strict || len(report.Warnings) == 0) {
			fmt.Println("Validation succeeded.")
		}
	}
	if !report.OK || (*strict && len(report.Warnings) > 0) {
		return errors.New("validation failed")
	}
	return nil
}

func cmdReindex(args []string) error {
	set := flag.NewFlagSet("reindex", flag.ContinueOnError)
	rootArg := rootFlag(set)
	if err := set.Parse(args); err != nil {
		return err
	}
	root, err := canonicalRoot(*rootArg)
	if err != nil {
		return err
	}
	return reindex(root)
}

func cmdPut(args []string) error {
	set := flag.NewFlagSet("put", flag.ContinueOnError)
	rootArg := rootFlag(set)
	id := set.String("id", "", "concept ID without .md")
	kind := set.String("kind", "", "log kind override")
	if err := set.Parse(args); err != nil {
		return err
	}
	root, err := canonicalRoot(*rootArg)
	if err != nil {
		return err
	}
	document, err := io.ReadAll(io.LimitReader(os.Stdin, 2*1024*1024))
	if err != nil {
		return err
	}
	if len(document) == 0 {
		return errors.New("empty concept document on stdin")
	}
	created, concept, err := putConcept(root, *id, document)
	if err != nil {
		return err
	}
	logKind := *kind
	if logKind == "" {
		if created {
			logKind = "Creation"
		} else {
			logKind = "Update"
		}
	}
	if err := updateLog(root, logKind, concept, ""); err != nil {
		return err
	}
	if err := reindex(root); err != nil {
		return err
	}
	report := validateBundle(root)
	if !report.OK {
		return errors.New("concept written but bundle validation failed")
	}
	fmt.Printf("%s %s\n", strings.ToLower(logKind), concept.ID)
	return nil
}

func cmdApplyReport(args []string) error {
	set := flag.NewFlagSet("apply-report", flag.ContinueOnError)
	rootArg := rootFlag(set)
	reportPath := set.String("report", "", "trusted memory-curator JSON report")
	backupArg := set.String("backup-dir", ".agent-loop/runtime/memory-backups", "transaction backup directory")
	if err := set.Parse(args); err != nil {
		return err
	}
	if *reportPath == "" {
		return errors.New("--report is required")
	}
	root, err := canonicalRoot(*rootArg)
	if err != nil {
		return err
	}
	reportBytes, err := os.ReadFile(*reportPath)
	if err != nil {
		return err
	}
	var report MemoryReport
	decoder := json.NewDecoder(bytes.NewReader(reportBytes))
	// Hook-added provenance fields are intentionally tolerated. The trusted hook
	// validates the role report before this deterministic transaction is invoked.
	if err := decoder.Decode(&report); err != nil {
		return fmt.Errorf("invalid memory report: %w", err)
	}
	if report.Role != "memory-curator" && report.Role != "brief-pattern-curator" {
		return errors.New("report role must be memory-curator or brief-pattern-curator")
	}
	if report.Role == "brief-pattern-curator" {
		if err := validateBriefPatternReport(report); err != nil {
			return err
		}
	}
	if report.Status == "NO_CHANGES" {
		result := ApplyResult{OK: true, Status: "NO_CHANGES", AppliedConceptIDs: []string{}}
		return printJSON(result)
	}
	if report.Status != "COMMIT" {
		return fmt.Errorf("report status %q is not applicable", report.Status)
	}
	if len(report.Operations) == 0 {
		return errors.New("COMMIT report has no operations")
	}
	if len(report.Operations) > maxReportOperations {
		return fmt.Errorf("COMMIT report exceeds maximum operations: %d > %d", len(report.Operations), maxReportOperations)
	}
	backupDir, err := filepath.Abs(*backupArg)
	if err != nil {
		return err
	}
	result, err := applyTransaction(root, backupDir, report)
	if err != nil {
		return err
	}
	return printJSON(result)
}

func validateBriefPatternReport(report MemoryReport) error {
	requiredConfirm := map[string]bool{
		"authority_envelope":  true,
		"memory_contract":     true,
		"stop_conditions":     true,
		"escalation_contract": true,
		"trigger_cadence":     true,
	}
	for index, operation := range report.Operations {
		if !strings.HasPrefix(operation.ConceptID, "loop-brief-patterns/") {
			return fmt.Errorf("brief pattern operation %d concept_id must be under loop-brief-patterns/", index)
		}
		frontmatter, _, err := parseFrontmatter(operation.Document)
		if err != nil {
			return fmt.Errorf("brief pattern operation %d: %w", index, err)
		}
		if scalar(frontmatter["type"]) != "Loop Brief Pattern" {
			return fmt.Errorf("brief pattern operation %d type must be Loop Brief Pattern", index)
		}
		reusePolicy := strings.ToLower(strings.TrimSpace(scalar(frontmatter["reuse_policy"])))
		if reusePolicy != "confirm" && reusePolicy != "suggest-only" && reusePolicy != "disabled" {
			return fmt.Errorf("brief pattern operation %d has invalid reuse_policy", index)
		}
		confirmed := map[string]bool{}
		for _, field := range stringList(frontmatter["confirmation_required_fields"]) {
			confirmed[field] = true
		}
		for field := range requiredConfirm {
			if !confirmed[field] {
				return fmt.Errorf("brief pattern operation %d confirmation_required_fields lacks %s", index, field)
			}
		}
		for _, key := range []string{"pattern_version", "task_class", "repository_kind", "risk_class", "trigger_kind"} {
			if strings.TrimSpace(scalar(frontmatter[key])) == "" {
				return fmt.Errorf("brief pattern operation %d lacks %s", index, key)
			}
		}
	}
	return nil
}

func cmdSearch(args []string) error {
	set := flag.NewFlagSet("search", flag.ContinueOnError)
	rootArg := rootFlag(set)
	query := set.String("query", "", "case-insensitive search query")
	limit := set.Int("limit", 20, "maximum results")
	jsonOutput := set.Bool("json", false, "emit JSON")
	if err := set.Parse(args); err != nil {
		return err
	}
	root, err := canonicalRoot(*rootArg)
	if err != nil {
		return err
	}
	terms := strings.Fields(strings.ToLower(*query))
	if len(terms) == 0 {
		return errors.New("--query must contain at least one term")
	}
	concepts, err := scanConcepts(root)
	if err != nil {
		return err
	}
	type scored struct {
		Concept Concept `json:"concept"`
		Score   int     `json:"score"`
	}
	var results []scored
	for _, concept := range concepts {
		metadata := strings.ToLower(strings.Join([]string{concept.ID, concept.Type, concept.Title, concept.Description, strings.Join(concept.Tags, " ")}, " "))
		body := strings.ToLower(concept.Body)
		score := 0
		matched := true
		for _, term := range terms {
			local := 0
			if strings.Contains(metadata, term) {
				local += 5
			}
			if strings.Contains(body, term) {
				local++
			}
			if local == 0 {
				matched = false
				break
			}
			score += local
		}
		if matched {
			concept.Body = ""
			concept.Frontmatter = nil
			results = append(results, scored{concept, score})
		}
	}
	sort.Slice(results, func(i, j int) bool {
		if results[i].Score != results[j].Score {
			return results[i].Score > results[j].Score
		}
		return results[i].Concept.ID < results[j].Concept.ID
	})
	if *limit > 0 && len(results) > *limit {
		results = results[:*limit]
	}
	if *jsonOutput {
		return printJSON(results)
	}
	for _, item := range results {
		fmt.Printf("%s\t%s\t%s\t%s\n", item.Concept.ID, item.Concept.Type, item.Concept.Title, item.Concept.Description)
	}
	return nil
}

func cmdMatchBriefPattern(args []string) error {
	set := flag.NewFlagSet("match-brief-pattern", flag.ContinueOnError)
	rootArg := rootFlag(set)
	taskClass := set.String("task-class", "", "abstract task class")
	repositoryKind := set.String("repository-kind", "", "repository kind")
	riskClass := set.String("risk-class", "", "risk class")
	triggerKind := set.String("trigger-kind", "", "trigger kind")
	limit := set.Int("limit", 8, "maximum results")
	jsonOutput := set.Bool("json", false, "emit JSON")
	if err := set.Parse(args); err != nil {
		return err
	}
	root, err := canonicalRoot(*rootArg)
	if err != nil {
		return err
	}
	concepts, err := scanConcepts(root)
	if err != nil {
		return err
	}
	type patternResult struct {
		ID                         string   `json:"id"`
		Title                      string   `json:"title"`
		Description                string   `json:"description"`
		Score                      int      `json:"score"`
		TaskClass                  string   `json:"task_class"`
		RepositoryKind             string   `json:"repository_kind"`
		RiskClass                  string   `json:"risk_class"`
		TriggerKind                string   `json:"trigger_kind"`
		ReusePolicy                string   `json:"reuse_policy"`
		ReusableFields             []string `json:"reusable_fields"`
		ConfirmationRequiredFields []string `json:"confirmation_required_fields"`
	}
	filters := map[string]string{
		"task_class":      strings.ToLower(strings.TrimSpace(*taskClass)),
		"repository_kind": strings.ToLower(strings.TrimSpace(*repositoryKind)),
		"risk_class":      strings.ToLower(strings.TrimSpace(*riskClass)),
		"trigger_kind":    strings.ToLower(strings.TrimSpace(*triggerKind)),
	}
	var results []patternResult
	for _, concept := range concepts {
		if concept.Type != "Loop Brief Pattern" || concept.Status != "active" || !strings.HasPrefix(concept.ID, "loop-brief-patterns/") {
			continue
		}
		score := 0
		matched := true
		for key, wanted := range filters {
			if wanted == "" {
				continue
			}
			actual := strings.ToLower(strings.TrimSpace(scalar(concept.Frontmatter[key])))
			switch {
			case actual == wanted:
				score += 4
			case actual == "*":
				score++
			default:
				matched = false
			}
			if !matched {
				break
			}
		}
		if !matched {
			continue
		}
		results = append(results, patternResult{
			ID: concept.ID, Title: concept.Title, Description: concept.Description, Score: score,
			TaskClass:                  scalar(concept.Frontmatter["task_class"]),
			RepositoryKind:             scalar(concept.Frontmatter["repository_kind"]),
			RiskClass:                  scalar(concept.Frontmatter["risk_class"]),
			TriggerKind:                scalar(concept.Frontmatter["trigger_kind"]),
			ReusePolicy:                scalar(concept.Frontmatter["reuse_policy"]),
			ReusableFields:             stringList(concept.Frontmatter["reusable_fields"]),
			ConfirmationRequiredFields: stringList(concept.Frontmatter["confirmation_required_fields"]),
		})
	}
	sort.Slice(results, func(i, j int) bool {
		if results[i].Score != results[j].Score {
			return results[i].Score > results[j].Score
		}
		return results[i].ID < results[j].ID
	})
	if *limit > 0 && len(results) > *limit {
		results = results[:*limit]
	}
	if *jsonOutput {
		return printJSON(results)
	}
	for _, item := range results {
		fmt.Printf("%s\t%d\t%s\t%s\n", item.ID, item.Score, item.Title, item.Description)
	}
	return nil
}

func cmdShow(args []string) error {
	set := flag.NewFlagSet("show", flag.ContinueOnError)
	rootArg := rootFlag(set)
	id := set.String("id", "", "concept ID")
	if err := set.Parse(args); err != nil {
		return err
	}
	root, err := canonicalRoot(*rootArg)
	if err != nil {
		return err
	}
	path, err := conceptPath(root, *id)
	if err != nil {
		return err
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	_, err = os.Stdout.Write(data)
	return err
}

func cmdStats(args []string) error {
	set := flag.NewFlagSet("stats", flag.ContinueOnError)
	rootArg := rootFlag(set)
	jsonOutput := set.Bool("json", false, "emit JSON")
	if err := set.Parse(args); err != nil {
		return err
	}
	root, err := canonicalRoot(*rootArg)
	if err != nil {
		return err
	}
	concepts, err := scanConcepts(root)
	if err != nil {
		return err
	}
	byType := map[string]int{}
	byStatus := map[string]int{}
	for _, concept := range concepts {
		byType[concept.Type]++
		status := concept.Status
		if status == "" {
			status = "unspecified"
		}
		byStatus[status]++
	}
	value := map[string]any{"concepts": len(concepts), "by_type": byType, "by_status": byStatus}
	if *jsonOutput {
		return printJSON(value)
	}
	fmt.Printf("Concepts: %d\n", len(concepts))
	printSortedCounts("Types", byType)
	printSortedCounts("Statuses", byStatus)
	return nil
}

func printSortedCounts(title string, values map[string]int) {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	fmt.Println(title + ":")
	for _, key := range keys {
		fmt.Printf("  %s: %d\n", key, values[key])
	}
}

func printJSON(value any) error {
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	return encoder.Encode(value)
}

func putConcept(root, id string, document []byte) (bool, Concept, error) {
	path, err := conceptPath(root, id)
	if err != nil {
		return false, Concept{}, err
	}
	if containsSecret(document) {
		return false, Concept{}, errors.New("concept contains a secret-like token; memory write refused")
	}
	concept, findings := parseConcept(root, path, document)
	for _, finding := range findings {
		if finding.Severity == "ERROR" {
			return false, Concept{}, fmt.Errorf("invalid concept: %s", finding.Message)
		}
	}
	created := true
	if _, err := os.Stat(path); err == nil {
		created = false
	} else if !errors.Is(err, os.ErrNotExist) {
		return false, Concept{}, err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return false, Concept{}, err
	}
	if err := atomicWrite(path, document, 0o644); err != nil {
		return false, Concept{}, err
	}
	return created, concept, nil
}

func applyTransaction(root, backupDir string, report MemoryReport) (ApplyResult, error) {
	rootParent := filepath.Dir(root)
	if err := os.MkdirAll(rootParent, 0o755); err != nil {
		return ApplyResult{}, err
	}
	temp, err := os.MkdirTemp(rootParent, ".llmwiki-txn-")
	if err != nil {
		return ApplyResult{}, err
	}
	defer os.RemoveAll(temp)
	if _, err := os.Stat(root); err == nil {
		if err := copyTree(root, temp); err != nil {
			return ApplyResult{}, err
		}
	} else if errors.Is(err, os.ErrNotExist) {
		if err := initializeAt(temp, "Project LLMWiki", "Curated, version-controlled knowledge for coding agents."); err != nil {
			return ApplyResult{}, err
		}
	} else {
		return ApplyResult{}, err
	}

	result := ApplyResult{OK: false, Status: "COMMIT", AppliedConceptIDs: []string{}}
	seen := map[string]bool{}
	for _, operation := range report.Operations {
		action := strings.ToUpper(operation.Action)
		if action != "UPSERT" && action != "DEPRECATE" {
			return ApplyResult{}, fmt.Errorf("unsupported memory operation %q", operation.Action)
		}
		if operation.ProposalID == "" {
			return ApplyResult{}, errors.New("memory operation lacks proposal_id")
		}
		if len(operation.Document) == 0 {
			return ApplyResult{}, fmt.Errorf("proposal %s has an empty document", operation.ProposalID)
		}
		if len(operation.Document) > maxConceptBytes {
			return ApplyResult{}, fmt.Errorf("proposal %s document exceeds %d bytes", operation.ProposalID, maxConceptBytes)
		}
		if seen[operation.ProposalID] {
			return ApplyResult{}, fmt.Errorf("duplicate proposal_id %q", operation.ProposalID)
		}
		seen[operation.ProposalID] = true
		existed := false
		destination, err := conceptPath(temp, operation.ConceptID)
		if err != nil {
			return ApplyResult{}, err
		}
		if _, err := os.Stat(destination); err == nil {
			existed = true
		}
		created, concept, err := putConcept(temp, operation.ConceptID, []byte(operation.Document))
		if err != nil {
			return ApplyResult{}, fmt.Errorf("proposal %s: %w", operation.ProposalID, err)
		}
		kind := "Update"
		if created {
			kind = "Creation"
			result.CreatedCount++
		} else {
			result.UpdatedCount++
		}
		if action == "DEPRECATE" || strings.EqualFold(concept.Status, "deprecated") {
			kind = "Deprecation"
			result.DeprecatedCount++
		}
		if existed && created {
			return ApplyResult{}, errors.New("internal transaction state inconsistency")
		}
		if err := updateLog(temp, kind, concept, ""); err != nil {
			return ApplyResult{}, err
		}
		result.AppliedConceptIDs = append(result.AppliedConceptIDs, operation.ConceptID)
	}
	if err := reindex(temp); err != nil {
		return ApplyResult{}, err
	}
	validation := validateBundle(temp)
	if !validation.OK {
		encoded, _ := json.Marshal(validation.Errors)
		return ApplyResult{}, fmt.Errorf("transaction bundle validation failed: %s", encoded)
	}
	result.ValidationWarnings = len(validation.Warnings)

	stamp := time.Now().UTC().Format("20060102T150405.000000000Z")
	backup := filepath.Join(backupDir, stamp)
	if err := os.MkdirAll(filepath.Dir(backup), 0o755); err != nil {
		return ApplyResult{}, err
	}
	oldExists := false
	if _, err := os.Stat(root); err == nil {
		oldExists = true
		if err := os.Rename(root, backup); err != nil {
			return ApplyResult{}, err
		}
		result.BackupPath = backup
	}
	if err := os.Rename(temp, root); err != nil {
		if oldExists {
			_ = os.Rename(backup, root)
		}
		return ApplyResult{}, err
	}
	result.OK = true
	sort.Strings(result.AppliedConceptIDs)
	return result, nil
}

func initializeAt(root, title, description string) error {
	dirs := []string{"concepts", "decisions", "constraints", "failure-patterns", "evaluation-rules", "recovery-patterns", "runbooks", "references", "loop-brief-patterns"}
	for _, dir := range dirs {
		if err := os.MkdirAll(filepath.Join(root, dir), 0o755); err != nil {
			return err
		}
	}
	body := fmt.Sprintf("---\nokf_version: \"0.1\"\ntitle: %s\ndescription: %s\n---\n\n# %s\n", yamlQuote(title), yamlQuote(description), title)
	if err := atomicWrite(filepath.Join(root, "index.md"), []byte(body), 0o644); err != nil {
		return err
	}
	log := "# Directory Update Log\n\n## " + time.Now().UTC().Format("2006-01-02") + "\n* **Initialization**: Created the OKF LLMWiki bundle.\n"
	return atomicWrite(filepath.Join(root, "log.md"), []byte(log), 0o644)
}

func copyTree(source, destination string) error {
	return filepath.WalkDir(source, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relative, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		target := filepath.Join(destination, relative)
		info, err := entry.Info()
		if err != nil {
			return err
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("symlink is not permitted in bundle: %s", path)
		}
		if entry.IsDir() {
			return os.MkdirAll(target, info.Mode().Perm())
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		return atomicWrite(target, data, info.Mode().Perm())
	})
}

func conceptPath(root, id string) (string, error) {
	id = strings.TrimSpace(strings.TrimSuffix(id, ".md"))
	if !conceptIDPattern.MatchString(id) || strings.Contains(id, "..") || strings.HasPrefix(id, "/") {
		return "", fmt.Errorf("invalid concept ID %q", id)
	}
	base := filepath.Base(id)
	if base == "index" || base == "log" {
		return "", errors.New("reserved filenames cannot be concept IDs")
	}
	rootAbs, err := filepath.Abs(root)
	if err != nil {
		return "", err
	}
	candidate := filepath.Join(rootAbs, filepath.FromSlash(id)+".md")
	candidateAbs, err := filepath.Abs(candidate)
	if err != nil {
		return "", err
	}
	relative, err := filepath.Rel(rootAbs, candidateAbs)
	if err != nil || strings.HasPrefix(relative, ".."+string(filepath.Separator)) || relative == ".." {
		return "", errors.New("concept path escapes bundle")
	}
	return candidateAbs, nil
}

func parseConcept(root, path string, data []byte) (Concept, []Finding) {
	relative, _ := filepath.Rel(root, path)
	display := filepath.ToSlash(relative)
	concept := Concept{Path: display, ID: strings.TrimSuffix(filepath.ToSlash(relative), ".md")}
	findings := []Finding{}
	if !utf8.Valid(data) {
		findings = append(findings, Finding{"ERROR", display, "file is not valid UTF-8"})
		return concept, findings
	}
	frontmatter, body, err := parseFrontmatter(string(data))
	if err != nil {
		findings = append(findings, Finding{"ERROR", display, err.Error()})
		return concept, findings
	}
	concept.Frontmatter = frontmatter
	concept.Body = body
	concept.Type = scalar(frontmatter["type"])
	concept.Title = scalar(frontmatter["title"])
	concept.Description = scalar(frontmatter["description"])
	concept.Status = strings.ToLower(scalar(frontmatter["status"]))
	concept.Timestamp = scalar(frontmatter["timestamp"])
	concept.Tags = stringList(frontmatter["tags"])
	if concept.Type == "" {
		findings = append(findings, Finding{"ERROR", display, "frontmatter type is required"})
	}
	profileRequired := []string{"title", "description", "timestamp", "status", "sensitivity", "authority", "confidence"}
	for _, key := range profileRequired {
		if strings.TrimSpace(scalar(frontmatter[key])) == "" {
			findings = append(findings, Finding{"ERROR", display, "LLMWiki profile requires frontmatter field: " + key})
		}
	}
	if concept.Timestamp != "" {
		if _, err := time.Parse(time.RFC3339, concept.Timestamp); err != nil {
			findings = append(findings, Finding{"ERROR", display, "timestamp must be RFC3339"})
		}
	}
	if concept.Status != "active" && concept.Status != "deprecated" {
		findings = append(findings, Finding{"ERROR", display, "status must be active or deprecated"})
	}
	sensitivity := strings.ToLower(scalar(frontmatter["sensitivity"]))
	if sensitivity != "public" && sensitivity != "internal" {
		findings = append(findings, Finding{"ERROR", display, "sensitivity must be public or internal; restricted knowledge is not allowed"})
	}
	if confidence := scalar(frontmatter["confidence"]); confidence != "" {
		value, err := strconv.ParseFloat(confidence, 64)
		if err != nil || value < 0 || value > 1 {
			findings = append(findings, Finding{"ERROR", display, "confidence must be a number between 0 and 1"})
		}
	}
	requiredSections := []string{"# Summary", "# Evidence", "# Applicability", "# Invalidation Conditions", "# Decision Log", "# Citations"}
	for _, section := range requiredSections {
		if !hasMarkdownHeading(body, section) {
			findings = append(findings, Finding{"ERROR", display, "LLMWiki profile requires body section: " + section})
		}
	}
	if containsSecret(data) {
		findings = append(findings, Finding{"ERROR", display, "secret-like token detected"})
	}
	return concept, findings
}

func hasMarkdownHeading(body, heading string) bool {
	normalized := strings.ReplaceAll(body, "\r\n", "\n")
	for _, line := range strings.Split(normalized, "\n") {
		if strings.TrimSpace(line) == heading {
			return true
		}
	}
	return false
}

func parseFrontmatter(document string) (Frontmatter, string, error) {
	document = strings.ReplaceAll(document, "\r\n", "\n")
	if !strings.HasPrefix(document, "---\n") {
		return nil, "", errors.New("concept must begin with YAML frontmatter")
	}
	end := strings.Index(document[4:], "\n---\n")
	if end < 0 {
		if strings.HasSuffix(document, "\n---") {
			end = len(document[4:]) - 4
		} else {
			return nil, "", errors.New("frontmatter closing delimiter not found")
		}
	}
	raw := document[4 : 4+end]
	bodyStart := 4 + end + len("\n---")
	body := strings.TrimPrefix(document[bodyStart:], "\n")
	parsed := Frontmatter{}
	scanner := bufio.NewScanner(strings.NewReader(raw))
	lineNo := 0
	for scanner.Scan() {
		lineNo++
		line := scanner.Text()
		if strings.ContainsRune(line, '\t') {
			return nil, "", fmt.Errorf("frontmatter line %d contains a tab", lineNo)
		}
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		if strings.HasPrefix(line, " ") {
			return nil, "", fmt.Errorf("frontmatter line %d uses nested YAML; this producer profile permits only top-level scalar or inline-list fields", lineNo)
		}
		key, value, ok := strings.Cut(line, ":")
		if !ok || !keyPattern.MatchString(strings.TrimSpace(key)) {
			return nil, "", fmt.Errorf("frontmatter line %d is not a valid top-level key/value", lineNo)
		}
		key = strings.TrimSpace(key)
		if _, exists := parsed[key]; exists {
			return nil, "", fmt.Errorf("duplicate frontmatter key %q", key)
		}
		parsedValue, err := parseYAMLValue(strings.TrimSpace(value))
		if err != nil {
			return nil, "", fmt.Errorf("frontmatter line %d: %w", lineNo, err)
		}
		parsed[key] = parsedValue
	}
	if err := scanner.Err(); err != nil {
		return nil, "", err
	}
	return parsed, body, nil
}

func parseYAMLValue(value string) (any, error) {
	if value == "" {
		return "", nil
	}
	if strings.HasPrefix(value, "[") {
		if !strings.HasSuffix(value, "]") {
			return nil, errors.New("unterminated inline list")
		}
		inner := strings.TrimSpace(value[1 : len(value)-1])
		if inner == "" {
			return []string{}, nil
		}
		parts, err := splitCSV(inner)
		if err != nil {
			return nil, err
		}
		values := make([]string, 0, len(parts))
		for _, part := range parts {
			values = append(values, unquote(strings.TrimSpace(part)))
		}
		return values, nil
	}
	if strings.HasPrefix(value, "|") || strings.HasPrefix(value, ">") || strings.HasPrefix(value, "{") {
		return nil, errors.New("block and flow-map YAML are outside the supported producer profile")
	}
	return unquote(stripComment(value)), nil
}

func splitCSV(value string) ([]string, error) {
	var result []string
	var current strings.Builder
	var quote rune
	escaped := false
	for _, r := range value {
		if escaped {
			current.WriteRune(r)
			escaped = false
			continue
		}
		if r == '\\' && quote != 0 {
			current.WriteRune(r)
			escaped = true
			continue
		}
		if quote != 0 {
			current.WriteRune(r)
			if r == quote {
				quote = 0
			}
			continue
		}
		if r == '\'' || r == '"' {
			quote = r
			current.WriteRune(r)
			continue
		}
		if r == ',' {
			result = append(result, current.String())
			current.Reset()
			continue
		}
		current.WriteRune(r)
	}
	if quote != 0 {
		return nil, errors.New("unterminated quoted list item")
	}
	result = append(result, current.String())
	return result, nil
}

func stripComment(value string) string {
	var quote rune
	escaped := false
	for index, r := range value {
		if escaped {
			escaped = false
			continue
		}
		if r == '\\' && quote != 0 {
			escaped = true
			continue
		}
		if quote != 0 {
			if r == quote {
				quote = 0
			}
			continue
		}
		if r == '\'' || r == '"' {
			quote = r
			continue
		}
		if r == '#' && (index == 0 || value[index-1] == ' ') {
			return strings.TrimSpace(value[:index])
		}
	}
	return strings.TrimSpace(value)
}

func unquote(value string) string {
	value = strings.TrimSpace(value)
	if len(value) >= 2 && ((value[0] == '"' && value[len(value)-1] == '"') || (value[0] == '\'' && value[len(value)-1] == '\'')) {
		if value[0] == '"' {
			if decoded, err := strconv.Unquote(value); err == nil {
				return decoded
			}
		}
		return strings.ReplaceAll(value[1:len(value)-1], "''", "'")
	}
	return value
}

func scalar(value any) string {
	switch typed := value.(type) {
	case string:
		return typed
	default:
		return fmt.Sprint(typed)
	}
}

func stringList(value any) []string {
	switch typed := value.(type) {
	case []string:
		return typed
	case string:
		if typed == "" {
			return nil
		}
		return []string{typed}
	default:
		return nil
	}
}

func scanConcepts(root string) ([]Concept, error) {
	var concepts []Concept
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("symlink is not permitted in OKF bundle: %s", path)
		}
		if entry.IsDir() || !strings.HasSuffix(strings.ToLower(entry.Name()), ".md") || entry.Name() == "index.md" || entry.Name() == "log.md" {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		concept, _ := parseConcept(root, path, data)
		concepts = append(concepts, concept)
		return nil
	})
	sort.Slice(concepts, func(i, j int) bool { return concepts[i].ID < concepts[j].ID })
	return concepts, err
}

func validateBundle(root string) ValidationReport {
	report := ValidationReport{OK: true, Root: root, Version: version, Errors: []Finding{}, Warnings: []Finding{}}
	info, err := os.Stat(root)
	if err != nil || !info.IsDir() {
		report.OK = false
		report.Errors = append(report.Errors, Finding{"ERROR", ".", "bundle root is missing or not a directory"})
		return report
	}
	_ = filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
		relative, _ := filepath.Rel(root, path)
		display := filepath.ToSlash(relative)
		if walkErr != nil {
			report.Errors = append(report.Errors, Finding{"ERROR", display, walkErr.Error()})
			return nil
		}
		info, err := entry.Info()
		if err != nil {
			report.Errors = append(report.Errors, Finding{"ERROR", display, err.Error()})
			return nil
		}
		if info.Mode()&os.ModeSymlink != 0 {
			report.Errors = append(report.Errors, Finding{"ERROR", display, "symlinks are not permitted in this LLMWiki profile"})
			return nil
		}
		if entry.IsDir() || !strings.HasSuffix(strings.ToLower(entry.Name()), ".md") {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			report.Errors = append(report.Errors, Finding{"ERROR", display, err.Error()})
			return nil
		}
		switch entry.Name() {
		case "index.md":
			rootIndex := filepath.Clean(path) == filepath.Join(root, "index.md")
			validateIndex(display, string(data), rootIndex, &report)
		case "log.md":
			validateLog(display, string(data), &report)
		default:
			report.Concepts++
			_, findings := parseConcept(root, path, data)
			for _, finding := range findings {
				if finding.Severity == "ERROR" {
					report.Errors = append(report.Errors, finding)
				} else {
					report.Warnings = append(report.Warnings, finding)
				}
			}
			validateLinks(root, path, string(data), &report)
		}
		return nil
	})
	report.OK = len(report.Errors) == 0
	return report
}

func validateIndex(path, content string, root bool, report *ValidationReport) {
	normalized := strings.ReplaceAll(content, "\r\n", "\n")
	if root && strings.HasPrefix(normalized, "---\n") {
		frontmatter, _, err := parseFrontmatter(normalized)
		if err != nil {
			report.Errors = append(report.Errors, Finding{"ERROR", path, "invalid root index frontmatter: " + err.Error()})
			return
		}
		if scalar(frontmatter["okf_version"]) != "0.1" {
			report.Warnings = append(report.Warnings, Finding{"WARN", path, "root index should declare okf_version: 0.1"})
		}
	} else if !root && strings.HasPrefix(normalized, "---\n") {
		report.Errors = append(report.Errors, Finding{"ERROR", path, "subdirectory index.md must not contain frontmatter"})
	}
}

func validateLog(path, content string, report *ValidationReport) {
	scanner := bufio.NewScanner(strings.NewReader(strings.ReplaceAll(content, "\r\n", "\n")))
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "## ") && !dateHeading.MatchString(line) {
			report.Errors = append(report.Errors, Finding{"ERROR", path, "log date heading must use YYYY-MM-DD"})
		}
	}
}

func validateLinks(root, source, content string, report *ValidationReport) {
	for _, match := range markdownLink.FindAllStringSubmatch(content, -1) {
		target := strings.TrimSpace(match[1])
		if target == "" || strings.HasPrefix(target, "#") || strings.Contains(target, "://") || strings.HasPrefix(target, "mailto:") {
			continue
		}
		target = strings.Split(target, "#")[0]
		var resolved string
		if strings.HasPrefix(target, "/") {
			resolved = filepath.Join(root, filepath.FromSlash(strings.TrimPrefix(target, "/")))
		} else {
			resolved = filepath.Join(filepath.Dir(source), filepath.FromSlash(target))
		}
		if strings.HasSuffix(target, "/") {
			resolved = filepath.Join(resolved, "index.md")
		}
		if _, err := os.Stat(resolved); errors.Is(err, os.ErrNotExist) {
			relative, _ := filepath.Rel(root, source)
			report.Warnings = append(report.Warnings, Finding{"WARN", filepath.ToSlash(relative), "broken cross-link: " + match[1]})
		}
	}
}

func reindex(root string) error {
	dirs := []string{}
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.IsDir() {
			info, err := entry.Info()
			if err != nil {
				return err
			}
			if info.Mode()&os.ModeSymlink != 0 {
				return fmt.Errorf("symlink is not permitted: %s", path)
			}
			dirs = append(dirs, path)
		}
		return nil
	})
	if err != nil {
		return err
	}
	sort.Slice(dirs, func(i, j int) bool {
		return strings.Count(dirs[i], string(filepath.Separator)) > strings.Count(dirs[j], string(filepath.Separator))
	})
	for _, dir := range dirs {
		if err := writeIndex(root, dir); err != nil {
			return err
		}
	}
	return nil
}

func writeIndex(root, dir string) error {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return err
	}
	var concepts []Concept
	var subdirs []string
	for _, entry := range entries {
		if entry.Name() == "index.md" || entry.Name() == "log.md" || strings.HasPrefix(entry.Name(), ".") {
			continue
		}
		if entry.IsDir() {
			subdirs = append(subdirs, entry.Name())
			continue
		}
		if !strings.HasSuffix(strings.ToLower(entry.Name()), ".md") {
			continue
		}
		path := filepath.Join(dir, entry.Name())
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		concept, findings := parseConcept(root, path, data)
		invalid := false
		for _, finding := range findings {
			if finding.Severity == "ERROR" {
				invalid = true
				break
			}
		}
		if !invalid {
			concepts = append(concepts, concept)
		}
	}
	sort.Strings(subdirs)
	sort.Slice(concepts, func(i, j int) bool {
		left, right := concepts[i].Title, concepts[j].Title
		if left == "" {
			left = concepts[i].ID
		}
		if right == "" {
			right = concepts[j].ID
		}
		return left < right
	})
	isRoot := filepath.Clean(dir) == filepath.Clean(root)
	var output strings.Builder
	if isRoot {
		frontmatter := "---\nokf_version: \"0.1\"\ntitle: \"Project LLMWiki\"\ndescription: \"Curated, version-controlled knowledge for coding agents.\"\n---\n"
		if existing, err := os.ReadFile(filepath.Join(dir, "index.md")); err == nil && strings.HasPrefix(string(existing), "---\n") {
			if end := strings.Index(string(existing)[4:], "\n---\n"); end >= 0 {
				frontmatter = string(existing)[:4+end+5]
			}
		}
		output.WriteString(frontmatter)
		output.WriteString("\n# LLMWiki\n\nThis index is generated by `okfctl reindex`. Read descriptions before opening individual concepts.\n")
	} else {
		relative, _ := filepath.Rel(root, dir)
		output.WriteString("# " + titleFromSlug(filepath.Base(relative)) + "\n\n")
		output.WriteString("Generated progressive-disclosure index.\n")
	}
	if len(subdirs) > 0 {
		output.WriteString("\n# Directories\n\n")
		for _, name := range subdirs {
			output.WriteString(fmt.Sprintf("* [%s](%s/) - Knowledge group.\n", titleFromSlug(name), name))
		}
	}
	if len(concepts) > 0 {
		output.WriteString("\n# Concepts\n\n")
		for _, concept := range concepts {
			title := concept.Title
			if title == "" {
				title = titleFromSlug(strings.TrimSuffix(filepath.Base(concept.Path), ".md"))
			}
			link := filepath.Base(concept.Path)
			description := concept.Description
			if description == "" {
				description = concept.Type
			}
			status := ""
			if concept.Status == "deprecated" {
				status = " [deprecated]"
			}
			output.WriteString(fmt.Sprintf("* [%s](%s)%s - %s\n", title, link, status, description))
		}
	}
	return atomicWrite(filepath.Join(dir, "index.md"), []byte(output.String()), 0o644)
}

func updateLog(root, kind string, concept Concept, message string) error {
	path := filepath.Join(root, "log.md")
	content, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		content = []byte("# Directory Update Log\n")
	} else if err != nil {
		return err
	}
	date := time.Now().UTC().Format("2006-01-02")
	heading := "## " + date
	title := concept.Title
	if title == "" {
		title = concept.ID
	}
	link := "/" + concept.ID + ".md"
	detail := concept.Description
	if message != "" {
		detail = message
	}
	bullet := fmt.Sprintf("* **%s**: [%s](%s)", kind, title, link)
	if detail != "" {
		bullet += " - " + strings.ReplaceAll(detail, "\n", " ")
	}
	bullet += ".\n"
	normalized := strings.ReplaceAll(string(content), "\r\n", "\n")
	if !strings.HasPrefix(normalized, "# Directory Update Log") {
		normalized = "# Directory Update Log\n\n" + normalized
	}
	if index := strings.Index(normalized, heading+"\n"); index >= 0 {
		insert := index + len(heading) + 1
		normalized = normalized[:insert] + bullet + normalized[insert:]
	} else {
		prefix := "# Directory Update Log\n\n"
		remainder := strings.TrimPrefix(normalized, prefix)
		normalized = prefix + heading + "\n" + bullet + "\n" + remainder
	}
	return atomicWrite(path, []byte(normalized), 0o644)
}

func atomicWrite(path string, data []byte, mode fs.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	temporary, err := os.CreateTemp(filepath.Dir(path), ".okfctl-*")
	if err != nil {
		return err
	}
	tempName := temporary.Name()
	defer os.Remove(tempName)
	if _, err := temporary.Write(data); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Sync(); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Chmod(mode); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	return os.Rename(tempName, path)
}

func containsSecret(data []byte) bool {
	text := string(data)
	for _, pattern := range secretPatterns {
		if pattern.MatchString(text) {
			return true
		}
	}
	return false
}

func yamlQuote(value string) string {
	encoded, _ := json.Marshal(value)
	return string(encoded)
}

func titleFromSlug(value string) string {
	value = strings.ReplaceAll(value, "-", " ")
	value = strings.ReplaceAll(value, "_", " ")
	words := strings.Fields(value)
	for index, word := range words {
		if word != "" {
			words[index] = strings.ToUpper(word[:1]) + word[1:]
		}
	}
	return strings.Join(words, " ")
}

func checksum(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

// Keep checksum linked into the binary for future deterministic manifest extensions.
var _ = checksum
