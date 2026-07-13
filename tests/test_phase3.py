from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from loopeng._paths import agent_root
from loopeng.audit.export import export_packet
from loopeng.audit.report import run_audit_report
from loopeng.inbox import collect_inbox
from loopeng.journal import append_event
from loopeng.run_stats import collect_run_stats


class Phase3Tests(unittest.TestCase):
    def test_export_packet_sanitizes_journal_and_contains_review_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            append_event(repo, "r1", {"kind": "run-start", "agent": "codex", "goal": "password=secret"})
            reports = repo / agent_root("state", "reports")
            reports.mkdir(parents=True)
            (reports / "r1.md").write_text("token=secret\n", encoding="utf-8")
            (reports / "r1.json").write_text(json.dumps({"run_id": "r1", "schema": 2}), encoding="utf-8")
            packet = export_packet(repo, "r1")
            self.assertTrue((packet / "manifest.json").is_file())
            self.assertNotIn("secret", (packet / "journal.json").read_text(encoding="utf-8"))
            self.assertTrue(json.loads((packet / "manifest.json").read_text(encoding="utf-8"))["sanitized"])
            self.assertTrue(json.loads((packet / "manifest.json").read_text(encoding="utf-8"))["packet_hash"])

    def test_sampling_due_is_reported_and_added_to_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            reports = repo / agent_root("state", "reports")
            reports.mkdir(parents=True)
            for index in range(1, 10):
                (reports / f"old-{index}.json").write_text(json.dumps({"run_id": f"old-{index}", "schema": 2}), encoding="utf-8")
            append_event(repo, "r10", {"kind": "run-start", "agent": "codex", "mode": "exploratory"})
            report = run_audit_report(repo, "r10")
            sidecar = json.loads((reports / "r10.json").read_text(encoding="utf-8"))
            self.assertTrue(any(alert["check_id"] == "external_review_due" for alert in sidecar["alerts"]))
            self.assertTrue(any(item["kind"] == "external-review" for item in collect_inbox(repo)))
            self.assertIn("external_review_due", report.read_text(encoding="utf-8"))

    def test_run_stats_keeps_discipline_outcome_counts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            for run_id, discipline, status in (("r1", "full", "pass"), ("r2", "baseline", "fail")):
                append_event(repo, run_id, {"kind": "run-start", "discipline": discipline, "timestamp": "2026-07-12T00:00:00+00:00"})
                append_event(repo, run_id, {"kind": "outcome", "status": status, "source": "verify", "timestamp": "2026-07-12T00:00:01+00:00"})
            stats = collect_run_stats(repo, ("7d",), "2026-07-13T00:00:00+00:00")
            self.assertEqual(stats["windows"]["7d"]["discipline"]["full"]["pass"], 1)
            self.assertEqual(stats["windows"]["7d"]["discipline"]["baseline"]["fail"], 1)


if __name__ == "__main__":
    unittest.main()
