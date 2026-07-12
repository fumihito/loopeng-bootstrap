from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from loopeng._paths import agent_root
from loopeng.audit.checks.common import AuditContext
from loopeng.audit.checks.budget_exceeded import check_budget_exceeded
from loopeng.audit.checks.destructive_command import check_destructive_command
from loopeng.audit.checks.high_risk_command import check_high_risk_command
from loopeng.audit.checks.journal_coverage import check_journal_coverage
from loopeng.audit.checks.learning_backlog import check_learning_backlog
from loopeng.audit.checks.out_of_repo_write import check_out_of_repo_write
from loopeng.audit.checks.protected_path_mutation import check_protected_path_mutation
from loopeng.audit.checks.secret_persistence import check_secret_persistence
from loopeng.audit.checks.single_author_memory_change import check_single_author_memory_change
from loopeng.audit.checks.skill_structure_violation import check_skill_structure_violation
from loopeng.audit.checks.unreviewed_claim_persisted import check_unreviewed_claim_persisted
from loopeng.audit.report import run_audit_report


DOT_AGENT = "." + "agent-loop"


def make_context(
    repo: Path,
    run_id: str,
    *,
    events: list[dict[str, object]] | None = None,
    changed_paths: tuple[str, ...] = (),
) -> AuditContext:
    return AuditContext(
        repo=repo,
        run_id=run_id,
        journal_path=repo / agent_root("state", "journal") / f"{run_id}.jsonl",
        events=tuple(events or ()),
        changed_paths=changed_paths,
        bundle_root=repo / "llmwiki",
        learning_root=repo / agent_root("state", "learning"),
        report_path=repo / agent_root("state", "reports") / f"{run_id}.md",
    )


class AuditChecksTests(unittest.TestCase):
    def test_destructive_command_check(self) -> None:
        positive = check_destructive_command(make_context(Path("."), "run", events=[{"kind": "command", "command": "rm -rf /"}]))
        negative = check_destructive_command(make_context(Path("."), "run", events=[{"kind": "command", "command": "echo safe"}]))
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_secret_persistence_check(self) -> None:
        positive = check_secret_persistence(make_context(Path("."), "run", events=[{"summary": "token=abc123"}]))
        negative = check_secret_persistence(make_context(Path("."), "run", events=[{"summary": "plain text"}]))
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_out_of_repo_write_check(self) -> None:
        positive = check_out_of_repo_write(make_context(Path("/tmp/repo"), "run", events=[{"path": "/tmp/outside"}]))
        negative = check_out_of_repo_write(make_context(Path("/tmp/repo"), "run", events=[{"path": "notes.md"}]))
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_protected_path_mutation_check(self) -> None:
        positive = check_protected_path_mutation(make_context(Path("."), "run", changed_paths=(DOT_AGENT + "/state/journal/run.jsonl",)))
        negative = check_protected_path_mutation(make_context(Path("."), "run", changed_paths=("docs/notes.md",)))
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_budget_exceeded_check(self) -> None:
        positive_events = [{"kind": "tool", "tool": "x"} for _ in range(41)]
        negative_events = [{"kind": "tool", "tool": "x"} for _ in range(2)]
        positive = check_budget_exceeded(make_context(Path("."), "run", events=positive_events))
        negative = check_budget_exceeded(make_context(Path("."), "run", events=negative_events))
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_journal_coverage_check(self) -> None:
        positive = check_journal_coverage(make_context(Path("."), "run", events=[{"kind": "mutation"}], changed_paths=("notes.md",)))
        negative = check_journal_coverage(make_context(Path("."), "run", events=[{"kind": "mutation", "path": "notes.md"}], changed_paths=("notes.md",)))
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_single_author_memory_change_check(self) -> None:
        positive = check_single_author_memory_change(
            make_context(
                Path("."),
                "run",
                events=[
                    {"kind": "memory_report", "actor": "codex"},
                    {"kind": "memory_apply", "actor": "codex"},
                ],
            )
        )
        negative = check_single_author_memory_change(
            make_context(
                Path("."),
                "run",
                events=[
                    {"kind": "memory_report", "actor": "codex"},
                    {"kind": "memory_apply", "actor": "claude"},
                ],
            )
        )
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_unreviewed_claim_persisted_check(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            bundle = repo / "llmwiki"
            bundle.mkdir()
            (bundle / "index.md").write_text("# llmwiki\n", encoding="utf-8")
            (bundle / "log.md").write_text("# log\n", encoding="utf-8")
            (bundle / "claims").mkdir()
            (bundle / "claims" / "one.md").write_text(
                "---\n"
                "type: Concept\n"
                "title: Claim\n"
                "description: claim\n"
                "tags: [claim]\n"
                "timestamp: '2026-07-10T00:00:00Z'\n"
                "status: active\n"
                "sensitivity: internal\n"
                "authority: test\n"
                "confidence: '1.0'\n"
                "evidence: self\n"
                "---\n"
                "# Summary\n"
                "Claim\n",
                encoding="utf-8",
            )
            positive = check_unreviewed_claim_persisted(make_context(repo, "run"))
            (bundle / "claims" / "one.md").write_text(
                "---\n"
                "type: Concept\n"
                "title: Claim\n"
                "description: claim\n"
                "tags: [claim]\n"
                "timestamp: '2026-07-10T00:00:00Z'\n"
                "status: active\n"
                "sensitivity: internal\n"
                "authority: test\n"
                "confidence: '1.0'\n"
                "evidence: reviewed\n"
                "---\n"
                "# Summary\n"
                "Claim\n",
                encoding="utf-8",
            )
            negative = check_unreviewed_claim_persisted(make_context(repo, "run"))
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_learning_backlog_check(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            learning_root = repo / agent_root("state", "learning")
            learning_root.mkdir(parents=True)
            (learning_root / "one.json").write_text("{}", encoding="utf-8")
            positive = check_learning_backlog(make_context(repo, "run"))
            (learning_root / "one.json").unlink()
            negative = check_learning_backlog(make_context(repo, "run"))
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_high_risk_command_check(self) -> None:
        positive = check_high_risk_command(make_context(Path("."), "run", events=[{"kind": "command", "command": "git push origin main"}]))
        negative = check_high_risk_command(make_context(Path("."), "run", events=[{"kind": "command", "command": "git status"}]))
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_skill_structure_violation_check(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            skill_root = repo / "adapters" / "shared" / "skills" / "frame-demo"
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text("---\nname: frame-demo\n---\n", encoding="utf-8")
            positive = check_skill_structure_violation(make_context(repo, "run"))
            (skill_root / "SKILL.md").write_text(
                "---\n"
                "name: frame-demo\n"
                "description: demo skill\n"
                "user-invocable: true\n"
                "---\n"
                "## Purpose\n"
                "Demo\n"
                "## When to use\n"
                "Demo\n"
                "## Workflow\n"
                "Demo\n"
                "## Output\n"
                "Demo\n"
                "## Exit\n"
                "Demo\n"
                "## Adjacent frames\n"
                "Demo\n",
                encoding="utf-8",
            )
            negative = check_skill_structure_violation(make_context(repo, "run"))
        self.assertTrue(positive)
        self.assertFalse(negative)

    def test_run_audit_report_generates_sections(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            (repo / "notes.md").write_text("hello\n", encoding="utf-8")
            journal = repo / agent_root("state", "journal") / "run-1.jsonl"
            journal.parent.mkdir(parents=True, exist_ok=True)
            journal.write_text(json.dumps({"kind": "mutation", "path": "notes.md"}) + "\n", encoding="utf-8")
            report_path = run_audit_report(repo, "run-1")
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("# Run Report run-1", text)
            self.assertIn("## Alerts", text)
            self.assertIn("## Blocked", text)
            self.assertIn("## Alerts", text)
