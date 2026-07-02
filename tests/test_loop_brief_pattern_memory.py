import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
FIELDS = {
    "outcome", "discovery_scope", "authority_envelope", "evaluation_contract",
    "persistence_contract", "learning_contract", "memory_contract", "stop_conditions",
    "escalation_contract", "trigger_cadence",
}


def load_hook(path: Path):
    spec = importlib.util.spec_from_file_location("pattern_memory_hook", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LoopBriefPatternMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls.tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=cls.repo, check=True)
        subprocess.run([sys.executable, str(KIT / "install.py"), "--repo", str(cls.repo)], check=True, capture_output=True, text=True)
        cls.hook = load_hook(cls.repo / ".agent-loop/hooks/loop_hook.py")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def call(self, event):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            rc = self.hook.handle(event, "codex")
        self.assertEqual(rc, 0)
        raw = stream.getvalue()
        return json.loads(raw) if raw.strip() else {}

    def event(self, name, session, turn):
        return {"hook_event_name": name, "session_id": session, "turn_id": turn, "cwd": str(self.repo)}

    def report(self, session, turn, role, body):
        event = self.event("SubagentStop", session, turn)
        event.update({"agent_type": role, "agent_id": "agent-" + role, "last_assistant_message": json.dumps(body)})
        return self.call(event)

    def brief(self):
        return {
            "outcome": "repair reproducible CI failures",
            "discovery_scope": ["failed CI"],
            "authority_envelope": {"allowed": ["local edits", "tests"], "forbidden": ["push", "production"], "approval_required": []},
            "evaluation_contract": ["targeted tests and regression tests pass"],
            "persistence_contract": ["record turn state"],
            "learning_contract": {"capture": ["failure patterns"], "validation": "meta-evaluator"},
            "memory_contract": {"format": "OKF 0.1", "input_pattern_memory": {"read": True, "save": True}, "excluded": ["secrets", "raw prompts"]},
            "stop_conditions": ["PASS", "budget exceeded"],
            "escalation_contract": ["value conflict", "production access"],
            "trigger_cadence": "on-event:ci-failure",
        }

    def gate(self, *, capture, accepted=None):
        accepted = accepted or []
        brief = self.brief()
        return {
            "role": "gatekeeper", "verdict": "READY", "mode": "AUTONOMOUS_LOOP",
            "condition_checklist": {field: True for field in FIELDS},
            "normalized_loop_brief": brief, "missing_conditions": [], "ambiguities": [],
            "questions_to_user": [], "risk_class": "medium", "rejection_reasons": [],
            "handoff_to_loop_brief_assistant": capture,
            "assistant_handoff_reason": "PATTERN_CAPTURE" if capture else "NONE",
            "handoff_to_sensemaker": "" if capture else "Frame the validated brief.",
            "brief_pattern_directive": {"action": "CAPTURE" if capture else "NONE", "reason": "explicit memory contract"},
            "brief_pattern_assessment": {
                "accepted_proposal_ids": accepted,
                "rejected_proposal_ids": [], "challenged_proposal_ids": [],
                "duplicate_pattern_ids": [], "required_corrections": [],
            },
            "validation_commands": [],
        }

    def assistant_report(self):
        return {
            "role": "loop-brief-assistant", "status": "READY_FOR_REVIEW", "interaction_mode": "PATTERN_CAPTURE",
            "draft_loop_brief": self.brief(), "resolved_conditions": sorted(FIELDS), "remaining_conditions": [],
            "assumptions": [], "questions_to_user": [], "conflicts": [], "handoff_to_gatekeeper": True,
            "pattern_retrieval": {"performed": True, "candidate_pattern_ids": [], "relevant_pattern_ids": [], "deprecated_pattern_ids": [], "unavailable_reason": None},
            "pattern_application": [],
            "pattern_proposals": [{
                "proposal_id": "brief-pattern.ci-repair.1",
                "concept_id": "loop-brief-patterns/ci-repair-medium",
                "action": "UPSERT", "title": "CI repair loop with local-only authority",
                "task_class": "ci-repair", "repository_kind": "software", "risk_class": "medium", "trigger_kind": "ci-failure",
                "reusable_fields": ["evaluation_contract", "persistence_contract", "learning_contract"],
                "confirmation_required_fields": ["authority_envelope", "memory_contract", "stop_conditions", "escalation_contract", "trigger_cadence"],
                "source_pattern_ids": [], "summary": "Reusable contract shape for local CI repair loops.",
                "sensitivity": "internal", "confidence": 0.85,
            }],
        }

    def pattern_document(self):
        return '''---
type: "Loop Brief Pattern"
title: "CI repair loop with local-only authority"
description: "Reusable contract shape for local CI repair loops."
tags: ["loop-brief-pattern", "ci-repair"]
timestamp: "2026-07-01T00:00:00Z"
status: "active"
sensitivity: "internal"
authority: "Gatekeeper accepted brief-pattern.ci-repair.1"
confidence: "0.85"
source_turns: ["pattern-turn"]
supersedes: []
review_after: "2026-10-01T00:00:00Z"
pattern_version: "1"
task_class: "ci-repair"
repository_kind: "software"
risk_class: "medium"
trigger_kind: "ci-failure"
reuse_policy: "confirm"
reusable_fields: ["evaluation_contract", "persistence_contract", "learning_contract"]
confirmation_required_fields: ["authority_envelope", "memory_contract", "stop_conditions", "escalation_contract", "trigger_cadence"]
---

# Summary

A reusable operating-contract shape for CI repair.

# Evidence

Derived from an explicit user-confirmed brief and independent Gatekeeper assessment.

# Applicability

Software repositories with reproducible CI failures and local-only automated changes.

# Invalidation Conditions

Do not reuse when production access, external messaging, or different risk ownership is required.

# Pattern

Suggest test evidence, state persistence, and learning review. Use placeholders for current outcome and discovery scope.

# Reuse Discipline

Every field must be confirmed. Authority, memory, stop, escalation, and trigger fields always require explicit confirmation.

# Decision Log

Created from proposal brief-pattern.ci-repair.1.

# Citations

No external citation is required for this internal operating-contract pattern.
'''

    def test_capture_commit_and_deterministic_match(self):
        session, turn = "pattern-session", "pattern-turn"
        self.call({**self.event("UserPromptSubmit", session, turn), "prompt": "repair CI and remember this input pattern"})
        self.assertEqual(self.report(session, turn, "gatekeeper", self.gate(capture=True)), {})
        stop = {**self.event("Stop", session, turn), "background_tasks": []}
        first = self.call(stop)
        self.assertIn("PATTERN_CAPTURE", first["reason"])

        self.assertEqual(self.report(session, turn, "loop-brief-assistant", self.assistant_report()), {})
        second = self.call(stop)
        self.assertIn("gatekeeper", second["reason"])

        self.assertEqual(self.report(session, turn, "gatekeeper", self.gate(capture=False, accepted=["brief-pattern.ci-repair.1"])), {})
        third = self.call(stop)
        self.assertIn("brief-pattern-curator", third["reason"])

        curator = {
            "role": "brief-pattern-curator", "status": "COMMIT",
            "processed_proposal_ids": ["brief-pattern.ci-repair.1"],
            "operations": [{"action": "UPSERT", "proposal_id": "brief-pattern.ci-repair.1", "concept_id": "loop-brief-patterns/ci-repair-medium", "document": self.pattern_document()}],
            "skipped_proposals": [], "conflicts": [], "validation_expectations": {"strict_okf": True},
        }
        self.assertEqual(self.report(session, turn, "brief-pattern-curator", curator), {})
        self.assertTrue((self.repo / "llmwiki/loop-brief-patterns/ci-repair-medium.md").is_file())
        commit = json.loads((self.repo / f".agent-loop/runtime/turns/{turn}/brief-pattern-commit.json").read_text())
        self.assertTrue(commit["ok"])

        matched = subprocess.run([
            str(self.repo / ".agent-loop/bin/okfctl"), "match-brief-pattern", "--root", "llmwiki",
            "--task-class", "ci-repair", "--repository-kind", "software", "--risk-class", "medium",
            "--trigger-kind", "ci-failure", "--json",
        ], cwd=self.repo, check=True, capture_output=True, text=True)
        results = json.loads(matched.stdout)
        self.assertEqual(results[0]["id"], "loop-brief-patterns/ci-repair-medium")
        self.assertNotIn("Pattern\n", matched.stdout)

        after = self.call(stop)
        message = after.get("reason") or after.get("stopReason") or ""
        self.assertIn("sensemaker", message)

    def test_pattern_suggestion_must_be_confirmed(self):
        session, turn = "reuse-session", "reuse-turn"
        self.call({**self.event("UserPromptSubmit", session, turn), "prompt": "set up another CI repair loop"})
        partial = self.brief()
        partial["authority_envelope"] = None
        gate = self.gate(capture=False)
        gate.update({
            "verdict": "NEEDS_INPUT",
            "condition_checklist": {field: field != "authority_envelope" for field in FIELDS},
            "normalized_loop_brief": partial,
            "missing_conditions": ["authority_envelope"],
            "questions_to_user": ["Confirm the authority envelope."],
            "handoff_to_loop_brief_assistant": True,
            "assistant_handoff_reason": "MISSING_INPUT",
            "handoff_to_sensemaker": "",
        })
        self.assertEqual(self.report(session, turn, "gatekeeper", gate), {})
        assistant = {
            "role": "loop-brief-assistant", "status": "ASK_USER", "interaction_mode": "CLARIFY",
            "draft_loop_brief": partial,
            "resolved_conditions": sorted(FIELDS - {"authority_envelope"}), "remaining_conditions": ["authority_envelope"],
            "assumptions": [], "questions_to_user": ["A matching pattern exists. Confirm or replace its local-only authority boundary."],
            "conflicts": [], "handoff_to_gatekeeper": False,
            "pattern_retrieval": {
                "performed": True,
                "candidate_pattern_ids": ["loop-brief-patterns/ci-repair-medium"],
                "relevant_pattern_ids": ["loop-brief-patterns/ci-repair-medium"],
                "deprecated_pattern_ids": [], "unavailable_reason": None,
            },
            "pattern_application": [{
                "pattern_id": "loop-brief-patterns/ci-repair-medium",
                "suggested_fields": ["authority_envelope"], "confirmed_fields": [], "rejected_fields": [],
            }],
            "pattern_proposals": [],
        }
        self.assertEqual(self.report(session, turn, "loop-brief-assistant", assistant), {})
        response = self.call({**self.event("Stop", session, turn), "background_tasks": []})
        self.assertIn("additional user input", response["stopReason"])


if __name__ == "__main__":
    unittest.main()
