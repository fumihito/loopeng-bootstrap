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
    spec = importlib.util.spec_from_file_location("direct_brief_hook", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DirectAndBriefAssistantTests(unittest.TestCase):
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

    def call(self, event, platform="codex"):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            rc = self.hook.handle(event, platform)
        self.assertEqual(rc, 0)
        raw = stream.getvalue()
        return json.loads(raw) if raw.strip() else {}

    def event(self, name, session, turn):
        return {"hook_event_name": name, "session_id": session, "turn_id": turn, "cwd": str(self.repo)}

    def report(self, session, turn, role, body):
        event = self.event("SubagentStop", session, turn)
        event.update({"agent_type": role, "agent_id": f"agent-{role}", "last_assistant_message": json.dumps(body)})
        return self.call(event)

    def gatekeeper(self, verdict, brief=None):
        brief = brief or {field: None for field in FIELDS}
        if not isinstance(brief.get("trigger_cadence"), str):
            brief = {**brief, "trigger_cadence": "external-user-prompt"}
        checklist = {field: bool(brief.get(field)) for field in FIELDS}
        return {
            "role": "gatekeeper",
            "verdict": verdict,
            "mode": "AUTONOMOUS_LOOP",
            "condition_checklist": checklist,
            "normalized_loop_brief": brief,
            "missing_conditions": sorted(field for field, ok in checklist.items() if not ok),
            "ambiguities": [],
            "questions_to_user": ["Which operations are allowed?"] if verdict == "NEEDS_INPUT" else [],
            "risk_class": "medium",
            "rejection_reasons": [],
            "handoff_to_loop_brief_assistant": verdict == "NEEDS_INPUT",
            "assistant_handoff_reason": "MISSING_INPUT" if verdict == "NEEDS_INPUT" else "NONE",
            "handoff_to_sensemaker": "Frame this brief." if verdict == "READY" else "",
            "brief_pattern_directive": {"action": "NONE", "reason": "pattern capture not requested"},
            "brief_pattern_assessment": {"accepted_proposal_ids": [], "rejected_proposal_ids": [], "challenged_proposal_ids": [], "duplicate_pattern_ids": [], "required_corrections": []},
            "validation_commands": [],
        }

    def test_direct_mode_bypasses_gatekeeper_and_is_read_only(self):
        session, turn = "direct-session", "direct-turn"
        start = self.event("UserPromptSubmit", session, turn)
        start["prompt"] = "direct: explain the failing test"
        output = self.call(start)
        self.assertIn("DIRECT_MODE", output["hookSpecificOutput"]["additionalContext"])
        state = json.loads((self.repo / f".agent-loop/runtime/sessions/{session}.json").read_text())
        self.assertEqual(state["routing_mode"], "DIRECT")
        self.assertFalse((self.repo / f".agent-loop/runtime/turns/{turn}/gatekeeper.json").exists())

        read = self.event("PreToolUse", session, turn)
        read.update({"tool_name": "Bash", "tool_input": {"command": "git status --porcelain"}})
        self.assertEqual(self.call(read), {})

        write = self.event("PreToolUse", session, turn)
        write.update({"tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch"}})
        denied = self.call(write)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("read-only", denied["hookSpecificOutput"]["permissionDecisionReason"])

        role_start = self.event("SubagentStart", session, turn)
        role_start.update({"agent_type": "gatekeeper", "agent_id": "g1"})
        self.assertIn("direct mode", self.call(role_start)["hookSpecificOutput"]["additionalContext"])

        stop = self.event("Stop", session, turn)
        stop["background_tasks"] = []
        self.assertEqual(self.call(stop), {})
        final = json.loads((self.repo / f".agent-loop/runtime/sessions/{session}.json").read_text())
        self.assertEqual(final["final_status"], "DIRECT_COMPLETE")

    def test_gatekeeper_needs_input_activates_assistant_and_persists_dialogue(self):
        session, turn = "brief-session", "brief-turn-1"
        start = self.event("UserPromptSubmit", session, turn)
        start["prompt"] = "build an autonomous repair loop"
        self.call(start)

        partial = {field: None for field in FIELDS}
        partial["outcome"] = "repair CI failures"
        partial["discovery_scope"] = ["failed CI"]
        gate = self.gatekeeper("NEEDS_INPUT", partial)
        self.assertEqual(self.report(session, turn, "gatekeeper", gate), {})

        stop = self.event("Stop", session, turn)
        stop["background_tasks"] = []
        continuation = self.call(stop)
        self.assertEqual(continuation["decision"], "block")
        self.assertIn("loop-brief-assistant", continuation["reason"])

        assistant = {
            "role": "loop-brief-assistant",
            "status": "ASK_USER",
            "interaction_mode": "CLARIFY",
            "draft_loop_brief": partial,
            "resolved_conditions": ["outcome", "discovery_scope"],
            "remaining_conditions": sorted(FIELDS - {"outcome", "discovery_scope"}),
            "assumptions": [],
            "questions_to_user": ["Which operations are allowed, forbidden, and approval-required?"],
            "conflicts": [],
            "handoff_to_gatekeeper": False,
            "pattern_retrieval": {"performed": True, "candidate_pattern_ids": [], "relevant_pattern_ids": [], "deprecated_pattern_ids": [], "unavailable_reason": None},
            "pattern_application": [],
            "pattern_proposals": [],
        }
        self.assertEqual(self.report(session, turn, "loop-brief-assistant", assistant), {})
        ask = self.call(stop)
        self.assertIn("additional user input", ask["stopReason"])
        session_report = self.repo / f".agent-loop/runtime/loop-brief-assistant-sessions/{session}.json"
        self.assertTrue(session_report.exists())

        next_turn = "brief-turn-2"
        answer = self.event("UserPromptSubmit", session, next_turn)
        answer["prompt"] = "Local edits and tests are allowed; push and production changes are forbidden."
        routed = self.call(answer)
        self.assertIn("answers outstanding Loop Brief Assistant questions", routed["hookSpecificOutput"]["additionalContext"])
        new_state = json.loads((self.repo / f".agent-loop/runtime/sessions/{session}.json").read_text())
        self.assertEqual(new_state["entry_role"], "loop-brief-assistant")
        self.assertTrue((self.repo / f".agent-loop/runtime/turns/{next_turn}/prior-loop-brief-assistant.json").exists())

        complete = {
            "outcome": "repair CI failures",
            "discovery_scope": ["failed CI"],
            "authority_envelope": {"allowed": ["local edits", "tests"], "forbidden": ["push", "production changes"], "approval_required": []},
            "evaluation_contract": ["targeted and regression tests pass"],
            "persistence_contract": ["record state"],
            "learning_contract": {"capture": ["failure patterns"], "validation": "meta-evaluator"},
            "memory_contract": {"format": "OKF 0.1", "eligible": ["failure patterns"], "excluded": ["secrets"], "promoter": "memory-curator"},
            "stop_conditions": ["PASS", "budget exceeded"],
            "escalation_contract": ["value conflict", "production access required"],
            "trigger_cadence": "external-user-prompt",
        }
        ready = {
            "role": "loop-brief-assistant",
            "status": "READY_FOR_REVIEW",
            "interaction_mode": "CLARIFY",
            "draft_loop_brief": complete,
            "resolved_conditions": sorted(FIELDS),
            "remaining_conditions": [],
            "assumptions": [],
            "questions_to_user": [],
            "conflicts": [],
            "handoff_to_gatekeeper": True,
            "pattern_retrieval": {"performed": True, "candidate_pattern_ids": [], "relevant_pattern_ids": [], "deprecated_pattern_ids": [], "unavailable_reason": None},
            "pattern_application": [],
            "pattern_proposals": [],
        }
        self.assertEqual(self.report(session, next_turn, "loop-brief-assistant", ready), {})
        review = self.call({**self.event("Stop", session, next_turn), "background_tasks": []})
        self.assertEqual(review["decision"], "block")
        self.assertIn("gatekeeper", review["reason"])

        gate_ready = self.gatekeeper("READY", complete)
        self.assertEqual(self.report(session, next_turn, "gatekeeper", gate_ready), {})
        self.assertFalse(session_report.exists())
        handoff = self.call({**self.event("Stop", session, next_turn), "background_tasks": []})
        self.assertEqual(handoff["decision"], "block")
        self.assertIn("sensemaker", handoff["reason"])

    def test_invalid_ready_assistant_with_assumptions_is_rejected(self):
        session, turn = "invalid-assistant", "invalid-turn"
        start = self.event("UserPromptSubmit", session, turn)
        start["prompt"] = "start a loop"
        self.call(start)
        partial = {field: [field] for field in FIELDS}
        self.report(session, turn, "gatekeeper", self.gatekeeper("NEEDS_INPUT", {**partial, "authority_envelope": None}))
        body = {
            "role": "loop-brief-assistant",
            "status": "READY_FOR_REVIEW",
            "interaction_mode": "CLARIFY",
            "draft_loop_brief": partial,
            "resolved_conditions": sorted(FIELDS),
            "remaining_conditions": [],
            "assumptions": ["authority guessed"],
            "questions_to_user": [],
            "conflicts": [],
            "handoff_to_gatekeeper": True,
            "pattern_retrieval": {"performed": True, "candidate_pattern_ids": [], "relevant_pattern_ids": [], "deprecated_pattern_ids": [], "unavailable_reason": None},
            "pattern_application": [],
            "pattern_proposals": [],
        }
        rejected = self.report(session, turn, "loop-brief-assistant", body)
        self.assertEqual(rejected["decision"], "block")
        self.assertIn("assumptions", rejected["reason"])


if __name__ == "__main__":
    unittest.main()
