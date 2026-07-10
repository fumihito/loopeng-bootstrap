from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from loopeng._paths import agent_root


class LoopengCliTests(unittest.TestCase):
    def test_journal_schedule_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            handoff = repo / agent_root("state", "handoff.json")
            handoff.parent.mkdir(parents=True, exist_ok=True)
            handoff.write_text(json.dumps({"source_turn_id": "turn-1", "goal": "repair", "summary": "ok"}), encoding="utf-8")

            event = json.dumps({"kind": "warning", "summary": "password=secret", "path": str(Path.home() / "demo")})
            journal = subprocess.run(
                [sys.executable, "-m", "loopeng", "journal", "add", "--run", "run-1", "--event", event, "--repo", str(repo)],
                text=True,
                capture_output=True,
                check=True,
            )
            journal_path = Path(journal.stdout.strip())
            self.assertTrue(journal_path.is_file())
            payload = journal_path.read_text(encoding="utf-8")
            self.assertIn("<redacted>", payload)
            self.assertNotIn(str(Path.home()), payload)

            schedule = subprocess.run(
                [sys.executable, "-m", "loopeng", "schedule", "next", "--repo", str(repo)],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("Next turn handoff", schedule.stdout)
            self.assertIn("source_turn_id: turn-1", schedule.stdout)

            report = subprocess.run(
                [sys.executable, "-m", "loopeng", "audit", "run", "--run", "run-1", "--repo", str(repo)],
                text=True,
                capture_output=True,
                check=True,
            )
            report_path = Path(report.stdout.strip())
            self.assertTrue(report_path.is_file())
            self.assertIn("Run Report run-1", report_path.read_text(encoding="utf-8"))

