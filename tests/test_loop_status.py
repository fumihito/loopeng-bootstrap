import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
SCRIPT = KIT / ".agent-loop/bin/loop_status.py"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def copy_policy_files(repo: Path) -> None:
    for rel in [".agent-loop/policy.json", ".agent-loop/scheduler-policy.json", ".agent-loop/learning-policy.json"]:
        write_json(repo / rel, json.loads((KIT / rel).read_text(encoding="utf-8")))


def write_turn(repo: Path, turn_id: str, *, started_at: str, completed_at: str | None, final_status: str | None, validation_ok: bool | None = None, brief_goal: str | None = None, scheduler_action: str | None = None, handoff_ready: bool = False, next_entry_role: str = "gatekeeper", unverified_claims: int = 0, include_reports: bool = True) -> None:
    turn_dir = repo / ".agent-loop/runtime/turns" / turn_id
    turn_dir.mkdir(parents=True, exist_ok=True)
    turn = {
        "turn_id": turn_id,
        "session_id": f"session-{turn_id}",
        "started_at": started_at,
        "routing_mode": "LOOP",
        "tool_calls": 1,
        "mutations": 1,
        "failures": 0,
        "watchdog": {"tripped": False, "reasons": []},
    }
    if completed_at is not None:
        turn["completed_at"] = completed_at
    if final_status is not None:
        turn["final_status"] = final_status
    write_json(turn_dir / "turn.json", turn)

    if include_reports and final_status == "PASS":
        write_json(turn_dir / "sensemaker.json", {
            "problem_signature": f"sig.{turn_id}",
            "prior_learning_considered": [],
            "learning_retrieval": {
                "performed": True,
                "candidate_lesson_ids": [],
                "relevant_lesson_ids": [],
                "unavailable_reason": None,
            },
            "memory_retrieval": {
                "performed": True,
                "candidate_concept_ids": [],
                "relevant_concept_ids": [],
                "deprecated_concept_ids": [],
                "unavailable_reason": None,
            },
        })
        write_json(turn_dir / "state-steward.json", {
            "learning_records": [],
            "question_updates": [],
            "memory_proposals": [],
        })
        write_json(turn_dir / "meta-evaluator.json", {
            "verdict": "PASS",
            "unverified": [],
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
        })
    elif final_status is not None:
        write_json(turn_dir / "meta-evaluator.json", {
            "verdict": final_status,
            "unverified": ["claim"] * unverified_claims,
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
        })

    if validation_ok is not None:
        write_json(turn_dir / "validation.json", {"ok": validation_ok})
    if brief_goal is not None:
        write_json(turn_dir / "loop-brief.json", {"goal": brief_goal, "outcome": brief_goal})
        write_json(turn_dir / "gatekeeper-prompt.json", {"prompt": f"Brief goal: {brief_goal}"})
    if handoff_ready:
        write_json(turn_dir / "next-turn.json", {
            "source_turn_id": turn_id,
            "session_id": f"session-{turn_id}",
            "routing_mode": "LOOP",
            "final_status": final_status,
            "ready_for_next_turn": True,
            "next_entry_role": next_entry_role,
            "trigger_kind": "external-user-prompt",
            "trigger_cadence": "immediate",
            "started_at": started_at,
            "completed_at": completed_at,
        })
        if scheduler_action:
            scheduler_dir = repo / ".agent-loop/runtime/scheduler"
            scheduler_dir.mkdir(parents=True, exist_ok=True)
            with (scheduler_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "observed_at": completed_at or started_at,
                    "turn_id": turn_id,
                    "scheduler_action": scheduler_action,
                }) + "\n")


class LoopStatusTests(unittest.TestCase):
    def test_text_reports_unstarted_state(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            copy_policy_files(repo)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo", str(repo), "--text"],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("未稼働", result.stdout)

    def test_html_classifies_turns_and_stays_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            copy_policy_files(repo)
            policy = json.loads((repo / ".agent-loop/policy.json").read_text(encoding="utf-8"))
            policy["status_thresholds"]["recent_turn_count"] = 20
            (repo / ".agent-loop/policy.json").write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            scheduler_policy = json.loads((repo / ".agent-loop/scheduler-policy.json").read_text(encoding="utf-8"))
            scheduler_policy["poll_interval_seconds"] = 5
            scheduler_policy["render_status_page"] = False
            (repo / ".agent-loop/scheduler-policy.json").write_text(json.dumps(scheduler_policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            learning_policy = json.loads((repo / ".agent-loop/learning-policy.json").read_text(encoding="utf-8"))
            learning_policy["minimum_turns_for_health"] = 5
            (repo / ".agent-loop/learning-policy.json").write_text(json.dumps(learning_policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (repo / ".agent-loop/runtime/turns").mkdir(parents=True, exist_ok=True)

            write_turn(repo, "turn-01", started_at="2026-07-01T00:00:00+00:00", completed_at="2026-07-01T00:10:00+00:00", final_status="PASS", validation_ok=True, brief_goal="secret goal phrase", handoff_ready=True, scheduler_action="triggered")
            write_turn(repo, "turn-02", started_at="2026-07-01T00:11:00+00:00", completed_at="2026-07-01T00:21:00+00:00", final_status="PASS", validation_ok=True, handoff_ready=True, scheduler_action="triggered")
            write_turn(repo, "turn-03", started_at="2026-07-01T00:22:00+00:00", completed_at="2026-07-01T00:32:00+00:00", final_status="PASS", validation_ok=False, handoff_ready=True)
            write_turn(repo, "turn-04", started_at="2026-07-01T00:33:00+00:00", completed_at="2026-07-01T00:43:00+00:00", final_status="PASS", validation_ok=True, handoff_ready=True, scheduler_action="triggered")
            write_turn(repo, "turn-05", started_at="2026-07-01T00:44:00+00:00", completed_at="2026-07-01T00:54:00+00:00", final_status="PASS", validation_ok=True, handoff_ready=True, scheduler_action="triggered")
            write_turn(repo, "turn-06", started_at="2026-07-01T00:55:00+00:00", completed_at="2026-07-01T01:05:00+00:00", final_status="REVISE", validation_ok=False)
            write_turn(repo, "turn-07", started_at="2026-07-01T01:06:00+00:00", completed_at="2026-07-01T01:16:00+00:00", final_status="ESCALATE", validation_ok=False, unverified_claims=2)
            write_turn(repo, "turn-08", started_at="2026-07-01T01:17:00+00:00", completed_at="2026-07-01T01:27:00+00:00", final_status="PROTECTED_DRIFT", validation_ok=False, unverified_claims=1)
            write_turn(repo, "turn-09", started_at="2026-07-01T01:28:00+00:00", completed_at=None, final_status=None)

            before = {str(path.relative_to(repo)) for path in repo.rglob("*") if path.is_file()}
            output = repo / ".agent-loop/runtime/status.html"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo", str(repo), "--html", str(output)],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(result.stdout.strip(), "")
            after = {str(path.relative_to(repo)) for path in repo.rglob("*") if path.is_file()}
            self.assertEqual(after - before, {".agent-loop/runtime/status.html"})
            html_text = output.read_text(encoding="utf-8")
            self.assertIn("status-pass", html_text)
            self.assertIn("status-amber", html_text)
            self.assertIn("status-red", html_text)
            self.assertIn("status-gray", html_text)
            self.assertIn("handoff-unconsumed", html_text)
            self.assertIn("Loop Closure Chain", html_text)
            self.assertIn("Trend", html_text)
            self.assertIn("Need Attention", html_text)
            self.assertNotIn("secret goal phrase", html_text)

            include_brief = repo / ".agent-loop/runtime/status-with-brief.html"
            subprocess.run(
                [sys.executable, str(SCRIPT), "--repo", str(repo), "--html", str(include_brief), "--include-brief"],
                text=True,
                capture_output=True,
                check=True,
            )
            brief_html = include_brief.read_text(encoding="utf-8")
            self.assertIn("secret goal phrase", brief_html)

            status_page = repo / ".agent-loop/runtime/status.html"
            status_page.unlink()
            scheduler_policy["render_status_page"] = True
            (repo / ".agent-loop/scheduler-policy.json").write_text(json.dumps(scheduler_policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            daemon = subprocess.run(
                [sys.executable, str(KIT / ".agent-loop/bin/next_turn_scheduler_daemon.py"), "--repo", str(repo), "--once"],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn('"processed_turns"', daemon.stdout)
            self.assertTrue(status_page.is_file())


if __name__ == "__main__":
    unittest.main()
