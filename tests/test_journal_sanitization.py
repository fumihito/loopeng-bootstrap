import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._helpers import class_requires_go

KIT = Path(__file__).resolve().parents[1]
HOOK = KIT / ".agent-loop/hooks/loop_hook.py"


def load_hook(path: Path):
    spec = importlib.util.spec_from_file_location("loop_hook_journal_tests", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_minimal_hook_tree(root: Path, mutated_source: str | None = None) -> None:
    (root / ".agent-loop/hooks").mkdir(parents=True, exist_ok=True)
    (root / "routing_hints.py").write_text((KIT / "routing_hints.py").read_text(encoding="utf-8"), encoding="utf-8")
    source = mutated_source if mutated_source is not None else HOOK.read_text(encoding="utf-8")
    (root / ".agent-loop/hooks/loop_hook.py").write_text(source, encoding="utf-8")


def run_journal_lint(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(KIT / "utils/journal_sanitization_lint.py"), "--root", str(root)],
        text=True,
        capture_output=True,
    )


def recursively_contains_forbidden_structure(value):
    forbidden = {"tool_input", "prompt", "content", "arguments", "stdout", "stderr", "message", "body", "text", "command", "file_path"}
    if isinstance(value, dict):
        for key, item in value.items():
            if key in forbidden:
                return True
            if recursively_contains_forbidden_structure(item):
                return True
    if isinstance(value, list):
        return any(recursively_contains_forbidden_structure(item) for item in value)
    return False


class JournalSanitizationTests(unittest.TestCase):
    def test_journal_helper_rejects_forbidden_keys(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            write_minimal_hook_tree(repo)
            hook = load_hook(repo / ".agent-loop/hooks/loop_hook.py")
            target = repo / "turn"
            hook.journal(target, "learning-state-read", tool_input={"file_path": ".agent-loop/state/learning/learning-index.json"})
            record = json.loads((target / "journal.jsonl").read_text(encoding="utf-8").strip())
            self.assertEqual(record["event_note"], "journal-key-rejected")
            self.assertNotIn("tool_input", record)
            self.assertFalse(record["content_logged"])
            self.assertFalse(record["arguments_logged"])

    def test_lint_rejects_raw_writes_and_forbidden_journal_keys(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            write_minimal_hook_tree(repo)
            pristine = run_journal_lint(repo)
            self.assertEqual(pristine.returncode, 0, pristine.stderr + pristine.stdout)

            raw_write = HOOK.read_text(encoding="utf-8") + '\nif False:\n    append_jsonl(Path("tmp") / "journal.jsonl", {"event": "bad"})\n'
            write_minimal_hook_tree(repo, raw_write)
            violated = run_journal_lint(repo)
            self.assertNotEqual(violated.returncode, 0)
            self.assertIn("raw journal.jsonl write outside journal()", violated.stdout)

            forbidden = HOOK.read_text(encoding="utf-8") + '\nif False:\n    journal(Path("tmp"), "bad", tool_input={"command": "git status"})\n'
            write_minimal_hook_tree(repo, forbidden)
            violated = run_journal_lint(repo)
            self.assertNotEqual(violated.returncode, 0)
            self.assertIn("forbidden journal key tool_input", violated.stdout)

@class_requires_go
class RuntimeJournalSanitizationTests(unittest.TestCase):
    def test_runtime_journal_is_subset_and_sanitized(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run([sys.executable, str(KIT / "install.py"), "--repo", str(repo)], check=True, capture_output=True, text=True, timeout=60)
            hook = load_hook(repo / ".agent-loop/hooks/loop_hook.py")

            def call(event):
                output = subprocess.run(
                    [sys.executable, str(repo / ".agent-loop/hooks/loop_hook.py"), "--platform", "claude"],
                    input=json.dumps(event),
                    text=True,
                    capture_output=True,
                    check=True,
                )
                return json.loads(output.stdout) if output.stdout.strip() else {}

            session = "journal-session"
            turn = "journal-turn"
            start = {"hook_event_name": "UserPromptSubmit", "session_id": session, "turn_id": turn, "cwd": str(repo), "prompt": "repair the defect"}
            call(start)
            call({"hook_event_name": "SubagentStop", "session_id": session, "turn_id": turn, "cwd": str(repo), "agent_id": "agent-gatekeeper", "agent_type": "gatekeeper", "last_assistant_message": json.dumps({
                "role": "gatekeeper",
                "verdict": "READY",
                "mode": "AUTONOMOUS_LOOP",
                "condition_checklist": {
                    "outcome": True,
                    "discovery_scope": True,
                    "authority_envelope": True,
                    "evaluation_contract": True,
                    "persistence_contract": True,
                    "learning_contract": True,
                    "memory_contract": True,
                    "stop_conditions": True,
                    "escalation_contract": True,
                    "trigger_cadence": True,
                },
                "normalized_loop_brief": {
                    "outcome": "repair the defect",
                    "discovery_scope": ["repository"],
                    "authority_envelope": {"allowed": ["local edits"], "forbidden": ["push"]},
                    "evaluation_contract": ["tests pass"],
                    "persistence_contract": ["record state"],
                    "learning_contract": {"capture": ["failure patterns"], "validation": "meta-evaluator", "review_after_turns": 10},
                    "memory_contract": {"format": "OKF 0.1", "bundle": "llmwiki", "eligible": ["Failure Pattern"], "excluded": ["secrets", "raw logs"], "promoter": "memory-curator"},
                    "stop_conditions": ["PASS"],
                    "escalation_contract": ["value conflict"],
                    "trigger_cadence": "external-user-prompt",
                },
                "missing_conditions": [],
                "ambiguities": [],
                "questions_to_user": [],
                "risk_class": "medium",
                "rejection_reasons": [],
                "handoff_to_loop_brief_assistant": False,
                "assistant_handoff_reason": "NONE",
                "handoff_to_sensemaker": "Frame the normalized brief.",
                "brief_pattern_directive": {"action": "NONE", "reason": "not requested"},
                "brief_pattern_assessment": {"accepted_proposal_ids": [], "rejected_proposal_ids": [], "challenged_proposal_ids": [], "duplicate_pattern_ids": [], "required_corrections": []},
                "validation_commands": [],
            })})
            call({"hook_event_name": "SubagentStop", "session_id": session, "turn_id": turn, "cwd": str(repo), "agent_id": "agent-sensemaker", "agent_type": "sensemaker", "last_assistant_message": json.dumps({
                "role": "sensemaker",
                "problem_frame": "x",
                "problem_signature": "test.problem",
                "observations": [],
                "inferences": [],
                "alternative_frames": [],
                "acceptance_criteria": [],
                "non_goals": [],
                "risks": [],
                "recommended_action": "y",
                "prior_learning_considered": [],
                "learning_retrieval": {"performed": True, "candidate_lesson_ids": [], "relevant_lesson_ids": [], "unavailable_reason": None},
                "memory_retrieval": {"performed": True, "candidate_concept_ids": [], "relevant_concept_ids": [], "deprecated_concept_ids": [], "unavailable_reason": None},
                "hypothesis_updates": [],
            })})
            call({"hook_event_name": "PreToolUse", "session_id": session, "turn_id": turn, "cwd": str(repo), "tool_name": "Read", "tool_input": {"file_path": ".agent-loop/state/learning/learning-index.json"}})

            journal_path = repo / ".agent-loop/runtime/turns/journal-turn/journal.jsonl"
            records = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            allowed = set(hook.JOURNAL_ALLOWED_KEYS) | {"content_logged", "arguments_logged"}
            for record in records:
                self.assertTrue(set(record).issubset(allowed))
                self.assertFalse(recursively_contains_forbidden_structure(record))
            learning_reads = [record for record in records if record.get("event") == "learning-state-read"]
            self.assertTrue(learning_reads)
            for record in learning_reads:
                self.assertNotIn("tool_input", record)

    def test_hook_self_test_includes_journal_lint(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            write_minimal_hook_tree(repo)
            proc = subprocess.run(
                [sys.executable, str(repo / ".agent-loop/hooks/loop_hook.py"), "--self-test", "--platform", "claude"],
                text=True,
                capture_output=True,
                cwd=repo,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("journal sanitization lint passed", proc.stdout.lower())
            self.assertIn("sanitized telemetry self-test", proc.stdout.lower())


if __name__ == "__main__":
    unittest.main()
