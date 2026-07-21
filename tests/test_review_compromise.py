from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from loopeng._paths import agent_root
from loopeng.audit.export import export_packet
from loopeng.inbox_model import actions_for
from loopeng.journal import append_event
from loopeng.review_contract import CONTRACT_VERSION
from loopeng.review_intake import intake, intake_auto
from loopeng.review_request import build_request
from loopeng.inbox_tui import meta_review_lines
from loopeng.review_calibration import summarize


class ReviewCompromiseTests(unittest.TestCase):
    def fixture(self):
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        repo = Path(td.name); subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "claim.py").write_text("print('claim')\n", encoding="utf-8")
        append_event(repo, "r1", {"kind": "run-start", "agent": "codex", "mode": "standard"})
        report_dir = repo / agent_root("state", "reports"); report_dir.mkdir(parents=True)
        (report_dir / "r1.json").write_text(json.dumps({"run_id": "r1", "schema": 2, "outcome": "pass", "alerts": [], "memory": {"applied": 0}}), encoding="utf-8")
        (report_dir / "r1.md").write_text("# Run Report r1\n", encoding="utf-8")
        packet = export_packet(repo, "r1")
        manifest = json.loads((packet / "manifest.json").read_text())
        build_request(repo, "r1")
        target = json.loads((packet / "manifest.json").read_text())["d5_target"]
        dims = [{"id": ident, "verdict": "pass", "evidence": [{"ref": (target if ident == "D5" else "journal:r1:1"), "note": "evidence"}], "note": "ok"} for ident in ("D1", "D2", "D3", "D4", "D5")]
        return repo, manifest["packet_hash"], dims

    def report(self, repo, packet_hash, dims, relation="self-family", meta=None):
        value = {"contract": CONTRACT_VERSION, "reviewer": {"model": "codex", "session": "new-session", "relation": relation}, "packet": {"run_id": "r1", "packet_hash": packet_hash}, "dimensions": dims, "overall": "pass", "findings": []}
        if meta: value["meta_review"] = meta
        path = repo / "review.json"; path.write_text(json.dumps(value), encoding="utf-8"); return path

    def test_self_family_requires_meta_and_auto_leaves_incoming(self):
        repo, packet_hash, dims = self.fixture()
        incoming = repo / agent_root("state", "reviews", "incoming"); incoming.mkdir(parents=True, exist_ok=True)
        path = incoming / "self.json"; path.write_text(json.dumps(json.loads(self.report(repo, packet_hash, dims).read_text())), encoding="utf-8")
        result = intake_auto(repo)
        self.assertFalse(result["accepted"]); self.assertIn("meta-review required", json.dumps(result))
        self.assertTrue(path.exists())

    def test_self_family_meta_accept_is_info(self):
        repo, packet_hash, dims = self.fixture()
        path = self.report(repo, packet_hash, dims, meta={"decision": "accept", "spot_dim": "D3", "spot_result": "ok"})
        result = intake(repo, path)
        self.assertTrue(result["accepted"], result); self.assertIn("self_review_info", result["warnings"])

    def test_d5_target_mismatch_is_rejected(self):
        repo, packet_hash, dims = self.fixture()
        dims[-1]["evidence"][0]["ref"] = "file:not-the-d5-target.py:1"
        result = intake(repo, self.report(repo, packet_hash, dims, relation="external"))
        self.assertFalse(result["accepted"]); self.assertTrue(any("d5_target mismatch" in item for item in result["errors"]))

    def test_self_family_is_explicit_in_inbox_actions(self):
        self.assertIn("meta-review", actions_for({"kind": "incoming-review", "relation": "self-family"}))

    def test_meta_review_spot_is_selected_at_display_time(self):
        repo, packet_hash, dims = self.fixture()
        path = self.report(repo, packet_hash, dims)
        with patch("loopeng.inbox_tui.secrets.choice", side_effect=["D2", "D5"]) as choice:
            first = meta_review_lines(repo, path)
            second = meta_review_lines(repo, path)
        self.assertEqual(first[1], "D2")
        self.assertEqual(second[1], "D5")
        self.assertEqual(choice.call_count, 2)
        self.assertNotEqual(first[1], second[1])

    def test_calibration_reports_due_and_dimension_rates(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td); reports = repo / agent_root("state", "reports"); reports.mkdir(parents=True)
            sidecar = {"schema": 2, "run_id": "r1", "alerts": [{"check_id": "external_review_due"}], "review_requirement": {"due": True, "relation": "external"}, "review": {"relation": "self-family", "dimensions": [{"id": "D1", "verdict": "pass"}, {"id": "D2", "verdict": "unable"}], "findings": []}}
            (reports / "r1.json").write_text(json.dumps(sidecar), encoding="utf-8")
            value = summarize(repo)
            self.assertEqual(value["due"], 1)
            self.assertEqual(value["required_external"], 1)
            self.assertEqual(value["by_relation"]["self-family"]["dimensions"]["D2"]["unable"], 1)


if __name__ == "__main__":
    unittest.main()
