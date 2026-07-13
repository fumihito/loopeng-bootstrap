from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from loopeng._paths import agent_root
from loopeng.audit.export import export_packet
from loopeng.journal import append_event
from loopeng.review_contract import CONTRACT_VERSION, REVIEW_DIMENSIONS
from loopeng.review_intake import intake


class ReviewIntakeTests(unittest.TestCase):
    def _fixture(self) -> tuple[Path, Path, Path]:
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        repo = Path(td.name)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "note.py").write_text("print('evidence')\n", encoding="utf-8")
        append_event(repo, "r1", {"kind": "run-start", "agent": "codex", "mode": "standard"})
        reports = repo / agent_root("state", "reports")
        reports.mkdir(parents=True)
        (reports / "r1.json").write_text(json.dumps({"run_id": "r1", "schema": 2, "outcome": "pass", "alerts": [], "memory": {"applied": 0}}), encoding="utf-8")
        (reports / "r1.md").write_text("# Run Report r1\n## Outcome\n", encoding="utf-8")
        packet = export_packet(repo, "r1")
        manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
        evidence = [
            {"id": "D1", "verdict": "pass", "evidence": [{"ref": "journal:r1:1", "note": "start"}], "note": "ok"},
            {"id": "D2", "verdict": "pass", "evidence": [{"ref": "sidecar:outcome", "note": "pass"}], "note": "ok"},
            {"id": "D3", "verdict": "pass", "evidence": [{"ref": "journal:r1:1", "note": "no apply"}], "note": "ok"},
            {"id": "D4", "verdict": "pass", "evidence": [{"ref": "sidecar:alerts", "note": "critical=0 warn=0"}], "note": "critical=0 warn=0"},
            {"id": "D5", "verdict": "pass", "evidence": [{"ref": "file:note.py:1", "note": "random code check"}], "note": "selected randomly"},
        ]
        report = repo / "review.json"
        report.write_text(json.dumps({"contract": CONTRACT_VERSION, "reviewer": {"model": "other-agent", "session": "s", "relation": "external"}, "packet": {"run_id": "r1", "packet_hash": manifest["packet_hash"]}, "dimensions": evidence, "overall": "pass", "findings": []}), encoding="utf-8")
        return repo, report, packet

    def test_valid_external_review_is_accepted_and_recorded(self) -> None:
        repo, report, _ = self._fixture()
        result = intake(repo, report)
        self.assertTrue(result["accepted"], result)
        journal = (repo / agent_root("state", "journal") / "r1.jsonl").read_text(encoding="utf-8")
        self.assertIn('external-review', journal)

    def test_hash_and_pointer_failures_are_rejected(self) -> None:
        repo, report, _ = self._fixture()
        value = json.loads(report.read_text(encoding="utf-8"))
        value["packet"]["packet_hash"] = "bad"
        value["dimensions"][0]["evidence"][0]["ref"] = "journal:r1:99"
        report.write_text(json.dumps(value), encoding="utf-8")
        result = intake(repo, report)
        self.assertFalse(result["accepted"])
        self.assertTrue(any("packet" in error for error in result["errors"]))

    def test_same_model_is_accepted_with_self_review_warning(self) -> None:
        repo, report, _ = self._fixture()
        value = json.loads(report.read_text(encoding="utf-8"))
        value["reviewer"]["model"] = "codex"
        report.write_text(json.dumps(value), encoding="utf-8")
        result = intake(repo, report)
        self.assertTrue(result["accepted"], result)
        self.assertIn("self_review", result["warnings"])

    def test_cross_checks_reject_outcome_memory_and_alert_count_contradictions(self) -> None:
        for change, expected in (("outcome", "review_inconsistency"), ("memory", "D3 says no memory"), ("alerts", "D4 critical")):
            repo, report, _ = self._fixture()
            sidecar = repo / agent_root("state", "reports", "r1.json")
            value = json.loads(sidecar.read_text(encoding="utf-8"))
            review = json.loads(report.read_text(encoding="utf-8"))
            if change == "outcome":
                value["outcome"] = "fail"
            elif change == "memory":
                value["memory"]["applied"] = 1
                review["dimensions"][2]["note"] = "no memory writes"
            else:
                value["alerts"] = [{"check_id": "x", "severity": "critical"}]
                review["dimensions"][3]["note"] = "critical=0 warn=0"
            sidecar.write_text(json.dumps(value), encoding="utf-8")
            packet = export_packet(repo, "r1")
            review["packet"]["packet_hash"] = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))["packet_hash"]
            report.write_text(json.dumps(review), encoding="utf-8")
            result = intake(repo, report)
            self.assertFalse(result["accepted"], (change, result))
            self.assertTrue(any(expected in error for error in result["errors"]), (change, result))


if __name__ == "__main__":
    unittest.main()
