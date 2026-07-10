from __future__ import annotations

import unittest
from unittest import mock
from pathlib import Path

from loopeng.journal import append_event, sanitize_event


class JournalSanitizationTests(unittest.TestCase):
    def test_sanitize_event_redacts_secrets_and_home(self) -> None:
        home = str(Path.home())
        event = {
            "command": f"password=secret {home}/work",
            "nested": {"token": "abc", "path": f"{home}/file"},
        }
        sanitized = sanitize_event(event)
        self.assertIn("<redacted>", sanitized["command"])
        self.assertNotIn(home, sanitized["command"])
        self.assertIn("<redacted>", sanitized["nested"]["token"])
        self.assertNotIn(home, sanitized["nested"]["path"])

    def test_append_event_writes_jsonl(self) -> None:
        with mock.patch("loopeng.journal.datetime") as fake_datetime:
            fake_datetime.now.return_value.isoformat.return_value = "2026-07-10T00:00:00+00:00"
            fake_datetime.timezone = __import__("datetime").timezone
            path = append_event(Path("."), "run-1", {"kind": "warning", "summary": "ok"})
        self.assertTrue(path.name.endswith(".jsonl"))
