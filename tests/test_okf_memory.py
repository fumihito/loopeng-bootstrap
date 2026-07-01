import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


def valid_document(title="Stale schema cache"):
    return f'''---
type: "Failure Pattern"
title: "{title}"
description: "A validated reusable failure pattern."
tags: ["schema", "cache"]
timestamp: "2026-07-01T00:00:00Z"
status: "active"
sensitivity: "internal"
authority: "meta-evaluator accepted MP-cache"
confidence: "0.90"
source_turns: ["turn-memory"]
supersedes: []
review_after: "2026-10-01T00:00:00Z"
---

# Summary

A stale schema cache can preserve obsolete state.

# Evidence

Regression test `schema-cache-regression` reproduced and verified the behavior.

# Applicability

Applies to versioned local schema caches.

# Invalidation Conditions

Invalid if cache keys become content-addressed.

# Related Concepts

None.

# Decision Log

## 2026-07-01 — Initial validation

Accepted after independent evaluation.

# Citations

No external citation is required for this repository-local observation.
'''


class OKFCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([str(KIT / ".agent-loop/bin/build-okfctl.sh")], cwd=KIT, check=True, capture_output=True, text=True, timeout=60)
        cls.binary = KIT / ".agent-loop/bin/okfctl.bin"

    def test_shell_wrappers_do_not_invoke_python(self):
        for rel in [".agent-loop/bin/okfctl", ".agent-loop/bin/build-okfctl.sh"]:
            text = (KIT / rel).read_text(encoding="utf-8").lower()
            self.assertNotIn("python", text)

    def test_put_validate_search_and_secret_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "wiki"
            subprocess.run([str(self.binary), "init", "--root", str(root)], check=True, capture_output=True, text=True)
            put = subprocess.run(
                [str(self.binary), "put", "--root", str(root), "--id", "failure-patterns/stale-schema-cache"],
                input=valid_document(), text=True, capture_output=True,
            )
            self.assertEqual(put.returncode, 0, put.stderr)
            validate = subprocess.run([str(self.binary), "validate", "--root", str(root), "--strict"], text=True, capture_output=True)
            self.assertEqual(validate.returncode, 0, validate.stderr)
            search = subprocess.run([str(self.binary), "search", "--root", str(root), "--query", "stale cache"], text=True, capture_output=True)
            self.assertIn("failure-patterns/stale-schema-cache", search.stdout)
            secret_value = "".join(["super", "secret", "value"])
            secret = valid_document("Unsafe") + "\npassword=" + secret_value + "\n"
            refused = subprocess.run(
                [str(self.binary), "put", "--root", str(root), "--id", "concepts/unsafe"],
                input=secret, text=True, capture_output=True,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertFalse((root / "concepts/unsafe.md").exists())

    def test_apply_report_accepts_hook_provenance_fields_transactionally(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "wiki"
            subprocess.run([str(self.binary), "init", "--root", str(root)], check=True, capture_output=True, text=True)
            report = {
                "role": "memory-curator",
                "status": "COMMIT",
                "processed_proposal_ids": ["MP-cache"],
                "operations": [{
                    "action": "UPSERT",
                    "proposal_id": "MP-cache",
                    "concept_id": "failure-patterns/stale-schema-cache",
                    "document": valid_document(),
                }],
                "skipped_proposals": [],
                "conflicts": [],
                "validation_expectations": {"profile": "agent-loop-llmwiki-v1"},
                "_trusted_subagent": True,
                "_mutation_epoch": 1,
            }
            path = base / "report.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            proc = subprocess.run([
                str(self.binary), "apply-report", "--root", str(root), "--report", str(path),
                "--backup-dir", str(base / "backups"),
            ], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertTrue(result["ok"])
            self.assertTrue((root / "failure-patterns/stale-schema-cache.md").is_file())
            self.assertTrue(any((base / "backups").iterdir()))


class MemoryHookIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run([sys.executable, str(KIT / "install.py"), "--repo", str(self.repo)], check=True, capture_output=True, text=True, timeout=60)
        hook_path = self.repo / ".agent-loop/hooks/loop_hook.py"
        spec = importlib.util.spec_from_file_location("memory_hook_test", hook_path)
        assert spec and spec.loader
        self.hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hook)

    def tearDown(self):
        self.temp.cleanup()

    def call(self, event):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = self.hook.handle(event)
        self.assertEqual(rc, 0)
        return json.loads(output.getvalue()) if output.getvalue().strip() else {}

    def event(self, name):
        return {"hook_event_name": name, "session_id": "memory-session", "turn_id": "turn-memory", "cwd": str(self.repo)}

    def report(self, role, body):
        event = self.event("SubagentStop")
        event.update({"agent_type": role, "agent_id": "agent-" + role, "last_assistant_message": json.dumps(body)})
        return self.call(event)

    def test_accepted_proposal_is_committed_only_through_curator(self):
        start = self.event("UserPromptSubmit")
        start["prompt"] = "repair and retain reusable knowledge"
        self.call(start)
        fields = ["outcome", "discovery_scope", "authority_envelope", "evaluation_contract", "persistence_contract", "learning_contract", "memory_contract", "stop_conditions", "escalation_contract", "trigger_cadence"]
        brief = {field: [field] for field in fields}
        gate = {
            "role": "gatekeeper", "verdict": "READY", "mode": "AUTONOMOUS_LOOP",
            "condition_checklist": {field: True for field in fields},
            "normalized_loop_brief": brief, "missing_conditions": [], "ambiguities": [],
            "questions_to_user": [], "risk_class": "medium", "rejection_reasons": [],
            "handoff_to_loop_brief_assistant": False, "assistant_handoff_reason": "NONE", "handoff_to_sensemaker": "frame it",
            "brief_pattern_directive": {"action": "NONE", "reason": "not requested"},
            "brief_pattern_assessment": {"accepted_proposal_ids": [], "rejected_proposal_ids": [], "challenged_proposal_ids": [], "duplicate_pattern_ids": [], "required_corrections": []},
        }
        self.assertEqual(self.report("gatekeeper", gate), {})
        sense = {
            "role": "sensemaker", "problem_frame": "cache defect", "problem_signature": "cache.schema.stale",
            "observations": [], "inferences": [], "alternative_frames": [], "acceptance_criteria": [],
            "non_goals": [], "risks": [], "recommended_action": "repair",
            "prior_learning_considered": [],
            "learning_retrieval": {"performed": True, "candidate_lesson_ids": [], "relevant_lesson_ids": [], "unavailable_reason": None},
            "memory_retrieval": {"performed": True, "candidate_concept_ids": [], "relevant_concept_ids": [], "deprecated_concept_ids": [], "unavailable_reason": None},
            "hypothesis_updates": [],
        }
        self.assertEqual(self.report("sensemaker", sense), {})
        direct = self.event("PreToolUse")
        direct.update({"tool_name": "Write", "tool_input": {"file_path": "llmwiki/concepts/bypass.md", "content": "secret"}})
        denied = self.call(direct)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        post = self.event("PostToolUse")
        post.update({"tool_name": "apply_patch", "tool_input": {"command": "patch"}, "tool_response": {"success": True}})
        self.call(post)
        proposal = {
            "proposal_id": "MP-cache", "action": "CREATE", "concept_id": "failure-patterns/stale-schema-cache",
            "type": "Failure Pattern", "title": "Stale schema cache", "description": "Reusable pattern",
            "tags": ["cache"], "source_lesson_ids": ["L-cache"], "evidence_refs": ["test:schema-cache-regression"],
            "citations": [], "related_concept_ids": [], "status": "active", "sensitivity": "internal",
            "confidence": 0.9, "applicability": "versioned schema caches", "invalidation_conditions": "content-addressed cache",
            "supersedes": [], "decision_log_entry": "Accepted after regression test",
        }
        steward = {
            "role": "state-steward", "facts": [], "inferences": [], "decisions": [], "open_questions": [],
            "artifacts": [], "next_state": "evaluate", "learning_records": [], "question_updates": [],
            "memory_proposals": [proposal],
        }
        self.assertEqual(self.report("state-steward", steward), {})
        meta = {
            "role": "meta-evaluator", "verdict": "PASS", "evaluation_basis": [], "evidence": [],
            "assumption_failures": [], "metric_gaming_risk": [], "unverified": [], "required_actions": [],
            "learning_assessment": {"accepted_lesson_ids": [], "rejected_lesson_ids": [], "challenged_lesson_ids": [], "superseded_lesson_ids": [], "reuse_assessment": [], "evaluation_changes": [], "knowledge_gaps": []},
            "memory_assessment": {"accepted_proposal_ids": ["MP-cache"], "rejected_proposal_ids": [], "challenged_proposal_ids": [], "duplicate_concept_ids": [], "citation_findings": [], "sensitivity_findings": [], "required_corrections": [], "memory_gaps": []},
        }
        self.assertEqual(self.report("meta-evaluator", meta), {})
        stop = self.event("Stop"); stop["background_tasks"] = []
        self.assertEqual(self.call(stop)["decision"], "block")
        curator = {
            "role": "memory-curator", "status": "COMMIT", "processed_proposal_ids": ["MP-cache"],
            "operations": [{"action": "UPSERT", "proposal_id": "MP-cache", "concept_id": "failure-patterns/stale-schema-cache", "document": valid_document()}],
            "skipped_proposals": [], "conflicts": [], "validation_expectations": {"profile": "agent-loop-llmwiki-v1"},
        }
        self.assertEqual(self.report("memory-curator", curator), {})
        self.assertTrue((self.repo / "llmwiki/failure-patterns/stale-schema-cache.md").is_file())
        self.assertTrue(json.loads((self.repo / ".agent-loop/runtime/turns/turn-memory/memory-commit.json").read_text())["ok"])
        self.assertEqual(self.call(stop), {})


class InstallerMemoryPreservationTests(unittest.TestCase):
    def test_existing_wiki_concept_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            concept = repo / "llmwiki/concepts/existing.md"
            concept.parent.mkdir(parents=True)
            original = valid_document("Existing project knowledge")
            concept.write_text(original, encoding="utf-8")
            subprocess.run([sys.executable, str(KIT / "install.py"), "--repo", str(repo)], check=True, capture_output=True, text=True, timeout=60)
            self.assertEqual(concept.read_text(encoding="utf-8"), original)
            self.assertTrue((repo / "llmwiki/index.md").is_file())
            self.assertTrue((repo / ".agent-loop/docs/OKF_LLMWIKI.md").is_file())
            self.assertTrue((repo / ".agent-loop/bin/okfctl").is_file())


if __name__ == "__main__":
    unittest.main()
