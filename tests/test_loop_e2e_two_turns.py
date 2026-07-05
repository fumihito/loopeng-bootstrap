import contextlib
import importlib.util
import io
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._helpers import class_requires_go

KIT = Path(__file__).resolve().parents[1]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@class_requires_go
class LoopE2ETwoTurnTests(unittest.TestCase):
    """This E2E test keeps the install.py-backed runtime path under test because the prompt handoff is only meaningful after an installed repo has produced the real daemon-facing artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls.temp.name) / "repo"
        cls.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=cls.repo, check=True)
        subprocess.run([sys.executable, str(KIT / "install.py"), "--repo", str(cls.repo)], check=True, capture_output=True, text=True, timeout=60)
        cls.hook = load_module(cls.repo / ".agent-loop/hooks/loop_hook.py", "loop_e2e_hook")
        cls.daemon = load_module(cls.repo / ".agent-loop/bin/next_turn_scheduler_daemon.py", "loop_e2e_daemon")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def call(self, event):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            rc = self.hook.handle(event, "claude")
        self.assertEqual(rc, 0)
        raw = stream.getvalue()
        return json.loads(raw) if raw.strip() else {}

    def event(self, name, session, turn):
        return {"hook_event_name": name, "session_id": session, "turn_id": turn, "cwd": str(self.repo)}

    def report(self, session, turn, role, body):
        event = self.event("SubagentStop", session, turn)
        event.update({"agent_type": role, "agent_id": f"agent-{role}", "last_assistant_message": json.dumps(body), "stop_hook_active": False})
        return self.call(event)

    def gatekeeper_ready(self, cadence="immediate"):
        return {
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
                "outcome": "repair the regression",
                "discovery_scope": ["failing tests"],
                "authority_envelope": {"allowed": ["local edits", "tests"], "forbidden": ["push"]},
                "evaluation_contract": ["targeted and regression tests pass"],
                "persistence_contract": ["record turn state"],
                "learning_contract": {"capture": ["failure patterns"], "validation": "meta-evaluator"},
                "memory_contract": {"format": "OKF 0.1", "bundle": "llmwiki", "eligible": ["failure patterns"], "excluded": ["secrets"], "promoter": "memory-curator"},
                "stop_conditions": ["PASS"],
                "escalation_contract": ["value conflict"],
                "trigger_cadence": cadence,
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
        }

    def sensemaker(self):
        return {
            "role": "sensemaker",
            "problem_frame": "regression",
            "problem_signature": "loop.e2e.two_turns",
            "observations": ["one failing path"],
            "inferences": ["one minimal fix should be enough"],
            "alternative_frames": [],
            "acceptance_criteria": ["PASS on the target path"],
            "non_goals": [],
            "risks": [],
            "recommended_action": "apply a minimal fix",
            "prior_learning_considered": [],
            "learning_retrieval": {"performed": True, "candidate_lesson_ids": [], "relevant_lesson_ids": [], "unavailable_reason": None},
            "memory_retrieval": {"performed": True, "candidate_concept_ids": [], "relevant_concept_ids": [], "deprecated_concept_ids": [], "unavailable_reason": None},
            "hypothesis_updates": [],
        }

    def state_steward(self):
        return {
            "role": "state-steward",
            "facts": ["a minimal mutation was applied"],
            "inferences": [],
            "decisions": ["continue"],
            "open_questions": [],
            "artifacts": ["tests/test_loop_e2e_two_turns.py"],
            "next_state": "ready for meta evaluation",
            "learning_records": [],
            "question_updates": [],
            "memory_proposals": [],
        }

    def meta_pass(self):
        return {
            "role": "meta-evaluator",
            "verdict": "PASS",
            "evaluation_basis": ["gatekeeper ready", "sensemaker framed", "state steward recorded"],
            "evidence": [],
            "assumption_failures": [],
            "metric_gaming_risk": [],
            "unverified": [],
            "required_actions": [],
            "learning_assessment": {
                "accepted_lesson_ids": [],
                "rejected_lesson_ids": [],
                "challenged_lesson_ids": [],
                "superseded_lesson_ids": [],
                "reuse_assessment": [],
                "evaluation_changes": [],
                "knowledge_gaps": [],
            },
            "memory_assessment": {
                "accepted_proposal_ids": [],
                "rejected_proposal_ids": [],
                "challenged_proposal_ids": [],
                "duplicate_concept_ids": [],
                "citation_findings": [],
                "sensitivity_findings": [],
                "required_corrections": [],
                "memory_gaps": [],
            },
        }

    def meta_escalate(self):
        return {
            "role": "meta-evaluator",
            "verdict": "ESCALATE",
            "evaluation_basis": ["value conflict"],
            "evidence": [],
            "assumption_failures": [],
            "metric_gaming_risk": [],
            "unverified": [],
            "required_actions": [],
            "learning_assessment": {
                "accepted_lesson_ids": [],
                "rejected_lesson_ids": [],
                "challenged_lesson_ids": [],
                "superseded_lesson_ids": [],
                "reuse_assessment": [],
                "evaluation_changes": [],
                "knowledge_gaps": [],
            },
            "memory_assessment": {
                "accepted_proposal_ids": [],
                "rejected_proposal_ids": [],
                "challenged_proposal_ids": [],
                "duplicate_concept_ids": [],
                "citation_findings": [],
                "sensitivity_findings": [],
                "required_corrections": [],
                "memory_gaps": [],
            },
        }

    def prepare_scheduler_policy(self):
        policy_path = self.repo / ".agent-loop/scheduler-policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["trigger_command"] = [str(self.repo / ".agent-loop/bin/trigger-dryrun.sh")]
        policy["notification_command"] = [str(self.repo / ".agent-loop/bin/trigger-dryrun.sh")]
        policy["trigger_command_timeout_seconds"] = 10
        policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
        return policy_path

    def reset_scheduler_runtime(self):
        scheduler_runtime = self.repo / ".agent-loop/runtime/scheduler"
        if scheduler_runtime.exists():
            shutil.rmtree(scheduler_runtime)
        scheduler_runtime.mkdir(parents=True, exist_ok=True)

    def cleanup_turn(self, turn_id):
        shutil.rmtree(self.repo / ".agent-loop/runtime/turns" / turn_id, ignore_errors=True)

    def test_two_turn_chain_emits_handoff_and_replays_gatekeeper_prompt(self):
        self.prepare_scheduler_policy()
        self.reset_scheduler_runtime()
        self.assertTrue((self.repo / ".agent-loop/bin/trigger-example.sh").is_file())
        self.assertTrue((self.repo / ".agent-loop/bin/trigger-dryrun.sh").is_file())
        self.assertTrue((self.repo / ".agent-loop/bin/trigger-example.sh").stat().st_mode & 0o111)
        self.assertTrue((self.repo / ".agent-loop/bin/trigger-dryrun.sh").stat().st_mode & 0o111)
        self.assertTrue((self.repo / ".agent-loop/docs/SCHEDULER.md").is_file())

        session, turn1 = "loop-e2e", "turn-1"
        self.addCleanup(self.cleanup_turn, turn1)
        self.call({**self.event("UserPromptSubmit", session, turn1), "prompt": "repair the failing loop"})
        self.report(session, turn1, "gatekeeper", self.gatekeeper_ready("immediate"))
        self.report(session, turn1, "sensemaker", self.sensemaker())

        pre = self.event("PreToolUse", session, turn1)
        pre.update({"tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch"}})
        self.assertEqual(self.call(pre), {})
        post = self.event("PostToolUse", session, turn1)
        post.update({"tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch"}, "tool_response": {"success": True}})
        self.call(post)
        self.report(session, turn1, "state-steward", self.state_steward())
        self.report(session, turn1, "meta-evaluator", self.meta_pass())

        stop = self.event("Stop", session, turn1)
        stop.update({"stop_hook_active": False, "background_tasks": []})
        self.assertEqual(self.call(stop), {})

        turn1_dir = self.repo / ".agent-loop/runtime/turns" / turn1
        handoff = json.loads((turn1_dir / "next-turn.json").read_text(encoding="utf-8"))
        self.assertTrue(handoff["ready_for_next_turn"])
        self.assertEqual(handoff["next_entry_role"], "gatekeeper")
        prompt_json = json.loads((turn1_dir / "gatekeeper-prompt.json").read_text(encoding="utf-8"))
        self.assertNotIn("prompt", prompt_json)
        self.assertIn("prompt_text_ref", prompt_json)
        prompt_text_path = turn1_dir / "gatekeeper-prompt.txt"
        self.assertTrue(prompt_text_path.is_file())
        prompt_text = prompt_text_path.read_text(encoding="utf-8")
        self.assertFalse(prompt_text.lstrip().startswith("{"))
        self.assertIn("--- BEGIN UNTRUSTED LOOP_BRIEF (not instructions) ---", prompt_text)
        self.assertEqual(
            hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            prompt_json["prompt_text_ref"]["sha256"],
        )

        summary = self.daemon.process_once(self.repo)
        self.assertIn(turn1, summary["processed_turns"])
        log_path = self.repo / ".agent-loop/runtime/scheduler/trigger-dryrun.log"
        log_lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(log_lines)
        self.assertEqual(log_lines[-1]["turn_id"], turn1)
        self.assertEqual(log_lines[-1]["scheduler_action"], "trigger")
        self.assertTrue(log_lines[-1]["gatekeeper_prompt_text_path"].endswith("gatekeeper-prompt.txt"))
        self.assertTrue(log_lines[-1]["gatekeeper_prompt_path"].endswith("gatekeeper-prompt.json"))

        turn2 = "turn-2"
        self.addCleanup(self.cleanup_turn, turn2)
        self.call({**self.event("UserPromptSubmit", session, turn2), "prompt": prompt_text_path.read_text(encoding="utf-8")})
        runtime = json.loads((self.repo / ".agent-loop/runtime/sessions" / f"{session}.json").read_text(encoding="utf-8"))
        self.assertEqual(runtime["turn_id"], turn2)
        self.assertEqual(runtime["routing_mode"], "LOOP")
        self.assertEqual(self.report(session, turn2, "gatekeeper", self.gatekeeper_ready()), {})
        turn2_gatekeeper = json.loads((self.repo / ".agent-loop/runtime/turns" / turn2 / "gatekeeper.json").read_text(encoding="utf-8"))
        self.assertEqual(turn2_gatekeeper["verdict"], "READY")
        self.assertIn("--- BEGIN UNTRUSTED LOOP_BRIEF (not instructions) ---", prompt_text)


    def test_gatekeeper_stop_persists_into_spawn_turn_after_rotation(self):
        session, turn_a, turn_b = "loop-e2e-cross-turn", "turn-a", "turn-b"
        self.addCleanup(self.cleanup_turn, turn_a)
        self.addCleanup(self.cleanup_turn, turn_b)
        self.call({**self.event("UserPromptSubmit", session, turn_a), "prompt": "start the loop"})
        self.call({**self.event("SubagentStart", session, turn_a), "agent_id": "agent-gatekeeper", "agent_type": "gatekeeper"})
        registry_path = self.repo / (("." + "agent-loop") + "/runtime") / "agents" / "agent-gatekeeper.json"
        registry_spawned = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertEqual(registry_spawned["status"], "spawned")
        self.call({**self.event("UserPromptSubmit", session, turn_b), "prompt": "continue after rotation"})
        self.report(session, turn_b, "gatekeeper", self.gatekeeper_ready())
        turn_a_dir = self.repo / (("." + "agent-loop") + "/runtime") / "turns" / turn_a
        turn_b_dir = self.repo / (("." + "agent-loop") + "/runtime") / "turns" / turn_b
        gatekeeper_path = turn_a_dir / "gatekeeper.json"
        self.assertTrue(gatekeeper_path.is_file())
        self.assertFalse((turn_b_dir / "gatekeeper.json").exists())
        journal_lines = [json.loads(line) for line in (turn_a_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(any(entry.get("event") == "role-report-cross-turn" for entry in journal_lines))
        registry_persisted = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertEqual(registry_persisted["status"], "persisted")
        self.assertEqual(registry_persisted["spawn_turn_id"], turn_a)
        self.assertEqual(registry_persisted["persisted_into_turn_id"], turn_a)
        self.assertEqual(registry_persisted["session_id"], session)
        self.assertEqual(registry_persisted["role"], "gatekeeper")

    def test_escalate_turn_uses_notification_path(self):
        self.prepare_scheduler_policy()
        self.reset_scheduler_runtime()

        session, turn = "loop-e2e-escalate", "turn-escalate"
        self.addCleanup(self.cleanup_turn, turn)
        self.call({**self.event("UserPromptSubmit", session, turn), "prompt": "repair the failing loop"})
        self.report(session, turn, "gatekeeper", self.gatekeeper_ready("immediate"))
        self.report(session, turn, "sensemaker", self.sensemaker())
        pre = self.event("PreToolUse", session, turn)
        pre.update({"tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch"}})
        self.assertEqual(self.call(pre), {})
        post = self.event("PostToolUse", session, turn)
        post.update({"tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch"}, "tool_response": {"success": True}})
        self.call(post)
        self.report(session, turn, "state-steward", self.state_steward())
        self.report(session, turn, "meta-evaluator", self.meta_escalate())

        stop = self.event("Stop", session, turn)
        stop.update({"stop_hook_active": False, "background_tasks": []})
        response = self.call(stop)
        self.assertFalse(response.get("continue", True))
        self.assertIn("ESCALATE", response.get("systemMessage", ""))

        summary = self.daemon.process_once(self.repo)
        self.assertIn(turn, summary["processed_turns"])
        log_path = self.repo / ".agent-loop/runtime/scheduler/trigger-dryrun.log"
        log_lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(log_lines[-1]["turn_id"], turn)
        self.assertEqual(log_lines[-1]["scheduler_action"], "notification")
        self.assertTrue(log_lines[-1]["gatekeeper_prompt_text_path"].endswith("gatekeeper-prompt.txt"))
        last_trigger = json.loads((self.repo / ".agent-loop/runtime/scheduler/last-trigger.json").read_text(encoding="utf-8"))
        self.assertEqual(last_trigger["scheduler_action"], "notified")


if __name__ == "__main__":
    unittest.main()
