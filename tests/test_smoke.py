import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import shutil
import tomllib
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
ROLES = ["gatekeeper", "loop-brief-assistant", "brief-pattern-curator", "sensemaker", "integrator", "governor", "state-steward", "watchdog-recovery", "meta-evaluator", "learning-auditor", "memory-curator"]
FRAME_SKILLS = ["frame-diag", "frame-plandev", "frame-plantask", "frame-first-principles", "frame-experiments", "frame-cynefin", "frame-smeac", "frame-proofread-ja", "frame-blind-spot", "frame-inertia", "frame-waiwad-grill", "frame-distributed-incident-analysis", "frame-critical-review", "frame-research-arch", "frame-research-tactics"]


def load_hook_module(path: Path):
    spec = importlib.util.spec_from_file_location("loop_hook_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls.tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=cls.repo, check=True, timeout=20)
        subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(cls.repo)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        cls.hook_path = cls.repo / ".agent-loop/hooks/loop_hook.py"
        cls.hook = load_hook_module(cls.hook_path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def call(self, event):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = self.hook.handle(event)
        self.assertEqual(rc, 0)
        raw = output.getvalue()
        return json.loads(raw) if raw.strip() else {}

    def event(self, name, session, turn):
        return {
            "hook_event_name": name,
            "session_id": session,
            "turn_id": turn,
            "cwd": str(self.repo),
        }

    def start(self, session, turn):
        event = self.event("UserPromptSubmit", session, turn)
        event["prompt"] = "modify code"
        return self.call(event)

    def report(self, session, turn, role, body, agent_type=None):
        event = self.event("SubagentStop", session, turn)
        event.update(
            {
                "agent_id": f"agent-{role}",
                "agent_type": agent_type or role,
                "last_assistant_message": json.dumps(body),
                "stop_hook_active": False,
            }
        )
        return self.call(event)

    @staticmethod
    def gatekeeper(verdict="READY"):
        return {
            "role": "gatekeeper",
            "verdict": verdict,
            "mode": "AUTONOMOUS_LOOP",
            "condition_checklist": {
                "outcome": True, "discovery_scope": True, "authority_envelope": verdict == "READY",
                "evaluation_contract": True, "persistence_contract": True, "learning_contract": True,
                "memory_contract": True, "stop_conditions": True, "escalation_contract": True, "trigger_cadence": True,
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
                "trigger_cadence": "one controlled turn",
            },
            "missing_conditions": [] if verdict == "READY" else ["authority_envelope"],
            "ambiguities": [],
            "questions_to_user": [] if verdict == "READY" else ["Which operations may the loop perform?"],
            "risk_class": "medium",
            "rejection_reasons": [],
            "handoff_to_loop_brief_assistant": verdict == "NEEDS_INPUT",
            "assistant_handoff_reason": "MISSING_INPUT" if verdict == "NEEDS_INPUT" else "NONE",
            "handoff_to_sensemaker": "Frame the normalized brief." if verdict == "READY" else "",
            "brief_pattern_directive": {"action": "NONE", "reason": "not requested"},
            "brief_pattern_assessment": {"accepted_proposal_ids": [], "rejected_proposal_ids": [], "challenged_proposal_ids": [], "duplicate_pattern_ids": [], "required_corrections": []},
        }

    @staticmethod
    def sensemaker():
        return {
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
            "learning_retrieval": {
                "performed": True,
                "candidate_lesson_ids": [],
                "relevant_lesson_ids": [],
                "unavailable_reason": None
            },
            "memory_retrieval": {
                "performed": True,
                "candidate_concept_ids": [],
                "relevant_concept_ids": [],
                "deprecated_concept_ids": [],
                "unavailable_reason": None
            },
            "hypothesis_updates": [],
        }

    def test_full_lifecycle_and_layout(self):
        json.loads((self.repo / ".codex/hooks.json").read_text())
        json.loads((self.repo / ".claude/settings.json").read_text())
        self.assertTrue((self.repo / "skills/sop-diag/SKILL.md").exists())
        self.assertTrue((self.repo / "skills/sop-list/SKILL.md").exists())
        self.assertTrue((self.repo / ".agents/skills").is_symlink())
        self.assertTrue((self.repo / ".claude/skills").is_symlink())
        self.assertEqual(__import__("os").readlink(self.repo / ".agents/skills"), "../skills/")
        self.assertEqual(__import__("os").readlink(self.repo / ".claude/skills"), "../skills/")
        self.assertTrue((self.repo / ".agents/skills/sop-diag/SKILL.md").exists())
        self.assertTrue((self.repo / ".agents/skills/sop-list/SKILL.md").exists())
        self.assertTrue((self.repo / ".claude/skills/sop-diag/SKILL.md").exists())
        self.assertTrue((self.repo / ".claude/skills/sop-list/SKILL.md").exists())
        self.assertTrue((self.repo / ".agent-loop/docs/DESIGN_PHILOSOPHY.md").exists())
        self.assertTrue((self.repo / ".agent-loop/docs/ARCHITECTURE.md").exists())
        self.assertTrue((self.repo / ".agent-loop/docs/HUMAN_SKILL_NAMESPACE.md").exists())
        self.assertTrue((self.repo / ".agent-loop/docs/LEARNING_OBSERVABILITY.md").exists())
        self.assertTrue((self.repo / ".agent-loop/bin/learning_health.py").exists())
        self.assertTrue((self.repo / ".agent-loop/bin/next_turn_scheduler_daemon.py").exists())
        self.assertTrue((self.repo / ".agent-loop/scheduler-policy.json").exists())
        self.assertTrue((self.repo / ".agent-loop/systemd/agent-loop-scheduler.service").exists())
        self.assertIn(str(self.repo), (self.repo / ".agent-loop/systemd/agent-loop-scheduler.service").read_text())
        self.assertTrue((self.repo / ".agent-loop/learning-policy.json").exists())
        self.assertTrue((self.repo / ".agents/skills/sop-learning-audit/SKILL.md").exists())
        for role in ROLES:
            tomllib.loads((self.repo / f".codex/agents/{role}.toml").read_text())
            self.assertTrue((self.repo / f".agents/skills/{role}/SKILL.md").exists())
            self.assertTrue((self.repo / f".claude/agents/{role}.md").exists())
            self.assertTrue((self.repo / f".claude/skills/{role}/SKILL.md").exists())
        for frame in FRAME_SKILLS:
            self.assertTrue((self.repo / f"skills/{frame}/SKILL.md").exists())
            self.assertTrue((self.repo / f".agents/skills/{frame}/SKILL.md").exists())
            self.assertTrue((self.repo / f".claude/skills/{frame}/SKILL.md").exists())

        session, turn = "integration-main", "turn-main"
        self.start(session, turn)
        pre = self.event("PreToolUse", session, turn)
        pre.update({"tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch"}})
        self.assertEqual(self.call(pre)["hookSpecificOutput"]["permissionDecision"], "deny")

        # Sensemaker cannot be accepted before Gatekeeper READY.
        self.report(session, turn, "sensemaker", self.sensemaker(), agent_type="general-purpose")
        self.assertEqual(self.call(pre)["hookSpecificOutput"]["permissionDecision"], "deny")
        rejected = self.report(session, turn, "sensemaker", self.sensemaker())
        self.assertEqual(rejected["decision"], "block")

        needs = self.gatekeeper("NEEDS_INPUT")
        self.report(session, turn, "gatekeeper", needs)
        stop_for_input = self.event("Stop", session, turn)
        stop_for_input.update({"stop_hook_active": False, "background_tasks": []})
        self.assertEqual(self.call(stop_for_input)["decision"], "block")
        assistant = {
            "role": "loop-brief-assistant",
            "status": "ASK_USER",
            "interaction_mode": "CLARIFY",
            "draft_loop_brief": needs["normalized_loop_brief"],
            "resolved_conditions": [field for field, ready in needs["condition_checklist"].items() if ready],
            "remaining_conditions": ["authority_envelope"],
            "assumptions": [],
            "questions_to_user": ["Which operations may the loop perform?"],
            "conflicts": [],
            "handoff_to_gatekeeper": False,
            "pattern_retrieval": {"performed": True, "candidate_pattern_ids": [], "relevant_pattern_ids": [], "deprecated_pattern_ids": [], "unavailable_reason": None},
            "pattern_application": [],
            "pattern_proposals": [],
        }
        self.report(session, turn, "loop-brief-assistant", assistant)
        self.assertIn("additional user input", self.call(stop_for_input)["stopReason"])
        self.assertEqual(self.call(pre)["hookSpecificOutput"]["permissionDecision"], "deny")

        self.report(session, turn, "gatekeeper", self.gatekeeper("READY"))
        self.assertEqual(self.call(pre)["hookSpecificOutput"]["permissionDecision"], "deny")

        # Codex Stop continuation acts like a new user prompt; the marker must preserve this turn.
        gate_ready_stop = self.event("Stop", session, turn)
        gate_ready_stop.update({"stop_hook_active": False, "background_tasks": []})
        continuation = self.call(gate_ready_stop)
        self.assertEqual(continuation["decision"], "block")
        continuation_prompt = self.event("UserPromptSubmit", session, "synthetic-continuation-turn")
        continuation_prompt["prompt"] = continuation["reason"]
        self.call(continuation_prompt)
        runtime_after_continuation = json.loads((self.repo / ".agent-loop/runtime/sessions/integration-main.json").read_text())
        self.assertEqual(runtime_after_continuation["turn_id"], turn)

        self.report(session, turn, "sensemaker", self.sensemaker())
        self.assertEqual(self.call(pre), {})
        self.assertTrue((self.repo / ".agent-loop/runtime/turns/turn-main/loop-brief.json").exists())

        role_pre = dict(pre)
        role_pre["agent_type"] = "meta-evaluator"
        self.assertEqual(self.call(role_pre)["hookSpecificOutput"]["permissionDecision"], "deny")

        perm = self.event("PermissionRequest", session, turn)
        perm.update({"tool_name": "Bash", "tool_input": {"command": "git push origin main"}})
        self.assertEqual(self.call(perm)["hookSpecificOutput"]["decision"]["behavior"], "deny")

        post = self.event("PostToolUse", session, turn)
        post.update({"tool_name": "apply_patch", "tool_input": {"command": "patch"}, "tool_response": {"success": True}})
        self.call(post)
        stop = self.event("Stop", session, turn)
        stop.update({"stop_hook_active": False, "background_tasks": []})
        self.assertEqual(self.call(stop)["decision"], "block")

        state = {
            "role": "state-steward",
            "facts": [],
            "inferences": [],
            "decisions": [],
            "open_questions": [],
            "artifacts": [],
            "next_state": "ready for meta evaluation",
            "learning_records": [{
                "lesson_id": "L-test-fix",
                "kind": "FAILURE_PATTERN",
                "statement": "The test defect requires the bounded fix.",
                "status": "PROPOSED",
                "evidence_refs": ["test:fixture"],
                "confidence": 0.8,
                "applicability": "test fixture",
                "invalidation_conditions": "fixture changes",
                "supersedes": [],
                "review_after_turns": 10
            }],
            "question_updates": [],
            "memory_proposals": [],
        }
        self.report(session, turn, "state-steward", state)
        self.assertEqual(self.call(stop)["decision"], "block")

        meta = {
            "role": "meta-evaluator",
            "verdict": "PASS",
            "evaluation_basis": [],
            "evidence": [],
            "assumption_failures": [],
            "metric_gaming_risk": [],
            "unverified": [],
            "required_actions": [],
            "learning_assessment": {
                "accepted_lesson_ids": ["L-test-fix"],
                "rejected_lesson_ids": [],
                "challenged_lesson_ids": [],
                "superseded_lesson_ids": [],
                "reuse_assessment": [],
                "evaluation_changes": [],
                "knowledge_gaps": []
            },
            "memory_assessment": {
                "accepted_proposal_ids": [],
                "rejected_proposal_ids": [],
                "challenged_proposal_ids": [],
                "duplicate_concept_ids": [],
                "citation_findings": [],
                "sensitivity_findings": [],
                "required_corrections": [],
                "memory_gaps": []
            },
        }
        self.report(session, turn, "meta-evaluator", meta)
        self.assertEqual(self.call(stop), {})
        learning_health = self.repo / ".agent-loop/state/learning/learning-health.json"
        self.assertTrue(learning_health.exists())
        health = json.loads(learning_health.read_text())
        self.assertEqual(health["window"]["all_completed_turns"], 1)
        self.assertEqual(health["metrics"]["accepted_lesson_count"], 1)
        handoff = json.loads((self.repo / ".agent-loop/runtime/turns/turn-main/next-turn.json").read_text())
        self.assertTrue(handoff["ready_for_next_turn"])
        self.assertEqual(handoff["next_entry_role"], "gatekeeper")
        scheduler = subprocess.run(
            [sys.executable, str(self.repo / ".agent-loop/bin/next_turn_scheduler.py"), "validate", "--repo", str(self.repo), "--turn-id", "turn-main"],
            text=True, capture_output=True, check=True,
        )
        self.assertEqual(scheduler.returncode, 0)

        fsession, fturn = "integration-failure", "turn-failure"
        self.start(fsession, fturn)
        self.report(fsession, fturn, "gatekeeper", self.gatekeeper("READY"))
        failure = self.event("PostToolUseFailure", fsession, fturn)
        failure.update({"tool_name": "Write", "tool_input": {"file_path": "x"}, "error": "failed"})
        for _ in range(6):
            self.call(failure)
        runtime_path = self.repo / ".agent-loop/runtime/sessions/integration-failure.json"
        runtime = json.loads(runtime_path.read_text())
        self.assertEqual(runtime["mutation_epoch"], 0)
        self.assertTrue(runtime["watchdog"]["tripped"])

    def test_scheduler_daemon_triggers_ready_handoff_once(self):
        policy_path = self.repo / ".agent-loop/scheduler-policy.json"
        policy = json.loads(policy_path.read_text())
        old_handoff = self.repo / ".agent-loop/runtime/turns/turn-main/next-turn.json"
        if old_handoff.exists():
            old_handoff.unlink()
        scheduler_runtime = self.repo / ".agent-loop/runtime/scheduler"
        if scheduler_runtime.exists():
            shutil.rmtree(scheduler_runtime)
        scheduler_runtime.mkdir(parents=True, exist_ok=True)
        policy["trigger_command"] = [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('triggered\\n', encoding='utf-8')",
            "{runtime_dir}/triggered.txt",
        ]
        policy["trigger_command_timeout_seconds"] = 10
        policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

        turn_dir = self.repo / ".agent-loop/runtime/turns/turn-scheduler"
        turn_dir.mkdir(parents=True, exist_ok=True)
        handoff = {
            "source_turn_id": "turn-scheduler",
            "session_id": "scheduler-session",
            "routing_mode": "LOOP",
            "final_status": "PASS",
            "ready_for_next_turn": True,
            "next_entry_role": "gatekeeper",
            "trigger_kind": "external-user-prompt",
            "started_at": "2026-07-01T00:00:00+00:00",
            "completed_at": "2026-07-01T00:01:00+00:00",
            "resume_hint": "Submit the next ordinary user message to enter Gatekeeper.",
        }
        (turn_dir / "next-turn.json").write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(self.repo / ".agent-loop/bin/next_turn_scheduler_daemon.py"), "--repo", str(self.repo), "--once"],
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=True,
            timeout=20,
        )
        self.assertIn("turn-scheduler", proc.stdout)
        self.assertTrue((self.repo / ".agent-loop/runtime/scheduler/triggered.txt").exists())
        state = json.loads((self.repo / ".agent-loop/runtime/scheduler/state.json").read_text())
        self.assertIn("turn-scheduler", state["processed_turns"])
        last_trigger = json.loads((self.repo / ".agent-loop/runtime/scheduler/last-trigger.json").read_text())
        self.assertEqual(last_trigger["turn_id"], "turn-scheduler")
        self.assertEqual(last_trigger["scheduler_action"], "triggered")

    def test_frame_prefix_routes_to_frame_mode(self):
        session, turn = "integration-frame", "turn-frame"
        event = self.event("UserPromptSubmit", session, turn)
        event["prompt"] = "frame-plandev: sketch a delivery plan"
        response = self.call(event)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[MANDATORY_FRAME_ROUTING]", context)
        self.assertIn("Routing mode: FRAME", context)
        self.assertIn("frame-plandev", context)

        runtime = json.loads((self.repo / ".agent-loop/runtime/sessions/integration-frame.json").read_text())
        self.assertEqual(runtime["routing_mode"], "FRAME")
        self.assertEqual(runtime["frame"]["required_skill"], "frame-plandev")
        self.assertTrue(runtime["frame"]["loaded"])

        frame_route = json.loads((self.repo / ".agent-loop/runtime/turns/turn-frame/frame-route.json").read_text())
        self.assertEqual(frame_route["skill_name"], "frame-plandev")
        self.assertFalse(frame_route["allow_mutations"])

    def test_integrator_is_required_before_mutation_when_policy_requests_it(self):
        policy_path = self.repo / ".agent-loop/policy.json"
        policy = json.loads(policy_path.read_text())
        policy["require_integrator_before_mutation"] = True
        policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

        session, turn = "integration-integrator", "turn-integrator"
        self.start(session, turn)
        self.report(session, turn, "gatekeeper", self.gatekeeper("READY"))
        self.report(session, turn, "sensemaker", self.sensemaker())

        pre = self.event("PreToolUse", session, turn)
        pre.update({"tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch"}})
        denied = self.call(pre)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("Integrator", denied["hookSpecificOutput"]["permissionDecisionReason"])

        integrator = {
            "role": "integrator",
            "status": "MERGED",
            "inputs": [
                {
                    "source_role": "sensemaker",
                    "summary": "Merged the candidate changes into one evaluation-ready frame.",
                }
            ],
            "merged_result": {
                "candidate_result": "apply_patch",
                "notes": "Ready for downstream evaluation.",
            },
            "conflicts": [],
            "resolution_strategy": "single merged candidate",
            "handoff_to_evaluator": True,
        }
        self.report(session, turn, "integrator", integrator)
        self.assertEqual(self.call(pre), {})

        # Gatekeeper state survives to the next user turn in the same session.
        next_turn = "turn-main-2"
        self.start(session, next_turn)
        prior = self.repo / f".agent-loop/runtime/turns/{next_turn}/prior-gatekeeper.json"
        self.assertTrue(prior.exists())
        self.assertEqual(json.loads(prior.read_text())["verdict"], "READY")

        # One real process invocation verifies the stdin/stdout entry point.
        process_event = self.event("SessionStart", "process-test", "process-turn")
        proc = subprocess.run(
            [sys.executable, str(self.hook_path)],
            cwd=self.repo,
            input=json.dumps(process_event),
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["hookEventName"], "SessionStart")


if __name__ == "__main__":
    unittest.main()
