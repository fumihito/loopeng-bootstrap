from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from loopeng._paths import agent_root


class LoopengCliTests(unittest.TestCase):
    def test_help_explains_top_level_and_nested_commands(self) -> None:
        japanese_env = {**os.environ, "LANG": "ja_JP.UTF-8"}
        top = subprocess.run(
            [sys.executable, "-m", "loopeng", "--help"],
            text=True,
            capture_output=True,
            env=japanese_env,
            check=True,
        )
        self.assertIn("監査可能なエージェント運用ループ", top.stdout)
        self.assertIn("okf       OKF LLMWiki", top.stdout)
        self.assertIn("review    過去の run 結果", top.stdout)

        okf = subprocess.run(
            [sys.executable, "-m", "loopeng", "okf", "--help"],
            text=True,
            capture_output=True,
            env=japanese_env,
            check=True,
        )
        self.assertIn("OKF 形式の LLMWiki バンドル", okf.stdout)
        self.assertIn("apply     検証済みレポート", okf.stdout)

        review = subprocess.run(
            [sys.executable, "-m", "loopeng", "review", "--help"],
            text=True,
            capture_output=True,
            env=japanese_env,
            check=True,
        )
        self.assertIn("未確認項目をトリアージ表示", review.stdout)
        self.assertIn("判断: go / alt / hold", review.stdout)

        english_env = {**os.environ, "LANG": "en_US.UTF-8"}
        english = subprocess.run(
            [sys.executable, "-m", "loopeng", "--help"],
            text=True,
            capture_output=True,
            env=english_env,
            check=True,
        )
        self.assertIn("CLI for operating auditable agent loops", english.stdout)
        self.assertIn("Review past run results", english.stdout)
        self.assertNotIn("監査可能なエージェント運用ループ", english.stdout)

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

            review_html = subprocess.run(
                [sys.executable, "-m", "loopeng", "review", "--format", "html", "--repo", str(repo)],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertTrue(review_html.stdout.startswith("<!doctype html>"))
            self.assertIn("Loop Review", review_html.stdout)

            dag_html = subprocess.run(
                [sys.executable, "-m", "loopeng", "review", "dag", "--format", "html", "--repo", str(repo)],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertTrue(dag_html.stdout.startswith("<!doctype html>"))
            self.assertIn("<svg", dag_html.stdout)
            self.assertTrue((repo / agent_root("state", "reports") / "loop-dag.html").is_file())
