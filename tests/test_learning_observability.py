import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class LearningObserverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run([sys.executable, str(KIT / "install.py"), "--repo", str(self.repo)], check=True, capture_output=True, text=True)

    def tearDown(self):
        self.tmp.cleanup()

    def turn(self, turn_id, index, signature, *, prior=None, lesson=None, accepted=None, reuse=None, questions=None):
        path = self.repo / ".agent-loop/runtime/turns" / turn_id
        write_json(path / "turn.json", {
            "turn_id": turn_id,
            "session_id": f"s{index}",
            "started_at": f"2026-07-{index+1:02d}T00:00:00+00:00",
            "completed_at": f"2026-07-{index+1:02d}T00:10:00+00:00",
            "routing_mode": "LOOP",
            "final_status": "PASS",
            "tool_calls": 5,
            "mutations": 1,
            "failures": 0,
            "watchdog": {"tripped": False, "reasons": []},
        })
        prior_items = prior or []
        relevant_ids = [str(item.get("lesson_id")) for item in prior_items if isinstance(item, dict) and item.get("lesson_id")]
        write_json(path / "sensemaker.json", {
            "problem_signature": signature,
            "prior_learning_considered": prior_items,
            "learning_retrieval": {
                "performed": True,
                "candidate_lesson_ids": relevant_ids,
                "relevant_lesson_ids": relevant_ids,
                "unavailable_reason": None,
            },
        })
        learning_records = []
        if lesson:
            learning_records.append({
                "lesson_id": lesson,
                "kind": "FAILURE_PATTERN",
                "statement": f"statement for {lesson}",
                "status": "PROPOSED",
                "evidence_refs": ["test:evidence"],
                "confidence": 0.8,
                "applicability": "test",
                "invalidation_conditions": "changed test",
                "supersedes": [],
                "review_after_turns": 10,
            })
        write_json(path / "state-steward.json", {
            "learning_records": learning_records,
            "question_updates": questions or [],
        })
        write_json(path / "meta-evaluator.json", {
            "verdict": "PASS",
            "learning_assessment": {
                "accepted_lesson_ids": accepted or [],
                "rejected_lesson_ids": [],
                "challenged_lesson_ids": [],
                "superseded_lesson_ids": [],
                "reuse_assessment": reuse or [],
                "evaluation_changes": [],
                "knowledge_gaps": [],
            },
        })

    def test_cross_turn_reuse_and_recurrence_are_observed(self):
        self.turn("t1", 0, "auth.race", lesson="L-auth-lock", accepted=["L-auth-lock"], questions=[{"question_id": "Q-auth", "status": "OPEN"}])
        self.turn(
            "t2", 1, "other.problem",
            prior=[{"lesson_id": "L-auth-lock", "disposition": "APPLIED"}],
            reuse=[{"lesson_id": "L-auth-lock", "outcome": "HELPFUL"}],
            questions=[{"question_id": "Q-auth", "status": "ANSWERED"}],
        )
        self.turn(
            "t3", 2, "auth.race",
            prior=[{"lesson_id": "L-auth-lock", "disposition": "CHALLENGED"}],
            reuse=[{"lesson_id": "L-auth-lock", "outcome": "HARMFUL"}],
        )
        result = subprocess.run(
            [sys.executable, str(self.repo / ".agent-loop/bin/learning_health.py"), "report", "--repo", str(self.repo)],
            text=True, capture_output=True, check=True,
        )
        summary = json.loads(result.stdout)
        metrics = summary["metrics"]
        self.assertEqual(metrics["accepted_lesson_count"], 1)
        self.assertEqual(metrics["turns_considering_prior_learning"], 2)
        self.assertEqual(metrics["helpful_reuse_count"], 1)
        self.assertEqual(metrics["harmful_reuse_count"], 1)
        self.assertEqual(metrics["problem_signature_recurrence_count"], 1)
        self.assertEqual(metrics["recurrence_after_learning_count"], 1)
        self.assertEqual(metrics["question_resolution_rate"], 1.0)
        self.assertEqual(summary["health"], "UNHEALTHY")  # critical harmful reuse and recurrence override the small-window UNKNOWN default
        payload = json.dumps(summary)
        self.assertNotIn("statement for", payload)
        observation = json.loads((self.repo / ".agent-loop/state/learning/turns/t1.json").read_text())
        self.assertNotIn("session_id", observation)
        self.assertIn("session_ref", observation)
        self.assertNotIn("L-auth-lock", json.dumps(summary["metrics"]))


    def test_small_clean_window_is_unknown(self):
        self.turn("t1", 0, "clean.problem")
        result = subprocess.run(
            [sys.executable, str(self.repo / ".agent-loop/bin/learning_health.py"), "report", "--repo", str(self.repo)],
            text=True, capture_output=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout)["health"], "UNKNOWN")


    def test_equal_window_trend_is_available(self):
        policy_path = self.repo / ".agent-loop/learning-policy.json"
        policy = json.loads(policy_path.read_text())
        policy["window_turns"] = 2
        policy["minimum_turns_for_health"] = 1
        policy_path.write_text(json.dumps(policy, indent=2) + "\n")
        self.turn("t1", 0, "p1", lesson="L-one", accepted=["L-one"])
        self.turn("t2", 1, "p2", prior=[{"lesson_id": "L-one", "disposition": "APPLIED"}], reuse=[{"lesson_id": "L-one", "outcome": "HELPFUL"}])
        self.turn("t3", 2, "p3", lesson="L-two", accepted=["L-two"])
        self.turn("t4", 3, "p4", prior=[{"lesson_id": "L-two", "disposition": "APPLIED"}], reuse=[{"lesson_id": "L-two", "outcome": "HELPFUL"}])
        result = subprocess.run(
            [sys.executable, str(self.repo / ".agent-loop/bin/learning_health.py"), "report", "--repo", str(self.repo)],
            text=True, capture_output=True, check=True,
        )
        summary = json.loads(result.stdout)
        self.assertTrue(summary["trend"]["comparison_available"])
        self.assertEqual(summary["trend"]["metric_deltas"]["learning_reuse_rate"], 0.0)

    def test_check_exit_code_can_fail_on_unhealthy(self):
        for index in range(5):
            self.turn(
                f"t{index}", index, "repeated.problem",
                lesson="L-repeated" if index == 0 else None,
                accepted=["L-repeated"] if index == 0 else [],
                prior=[{"lesson_id": "L-repeated", "disposition": "APPLIED"}] if index else [],
                reuse=[{"lesson_id": "L-repeated", "outcome": "HARMFUL"}] if index == 4 else [],
            )
        result = subprocess.run(
            [sys.executable, str(self.repo / ".agent-loop/bin/learning_health.py"), "check", "--repo", str(self.repo), "--fail-on", "unhealthy"],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 4)
        self.assertEqual(json.loads(result.stdout)["health"], "UNHEALTHY")


if __name__ == "__main__":
    unittest.main()
