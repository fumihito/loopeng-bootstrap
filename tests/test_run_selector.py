from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from loopeng._paths import agent_root
from loopeng.doctor import inspect
from loopeng.journal import append_event
from loopeng.hooks.codex import normalize as normalize_codex
from loopeng.hooks.handler import handle
from loopeng.run import resolve_run_selector


class RunSelectorTests(unittest.TestCase):
    def repo(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        holder = tempfile.TemporaryDirectory()
        root = Path(holder.name)
        (root / agent_root("state", "journal")).mkdir(parents=True)
        (root / agent_root("state", "reports")).mkdir(parents=True)
        return holder, root

    def start(self, root: Path, run_id: str, timestamp: str) -> None:
        append_event(root, run_id, {"kind": "run-start", "timestamp": timestamp})

    def test_latest_uses_timestamp_then_run_id_descending(self) -> None:
        holder, root = self.repo()
        try:
            self.start(root, "a", "2026-07-13T00:00:00+00:00")
            self.start(root, "z", "2026-07-13T00:00:00+00:00")
            stderr = StringIO()
            with redirect_stderr(stderr):
                self.assertEqual(resolve_run_selector(root, "latest"), "z")
            self.assertIn("selector 'latest' -> z", stderr.getvalue())
        finally:
            holder.cleanup()

    def test_due_excludes_accepted_review_and_fail_selects_latest(self) -> None:
        holder, root = self.repo()
        try:
            self.start(root, "due-old", "2026-07-13T00:00:00+00:00")
            self.start(root, "due-new", "2026-07-13T01:00:00+00:00")
            for run_id in ("due-old", "due-new"):
                (root / agent_root("state", "reports") / f"{run_id}.json").write_text(json.dumps({"alerts": [{"check_id": "external_review_due"}]}), encoding="utf-8")
            append_event(root, "due-old", {"kind": "external-review", "accepted_by": "loopeng review intake"})
            self.assertEqual(resolve_run_selector(root, "latest-due"), "due-new")
            self.start(root, "fail-old", "2026-07-13T02:00:00+00:00")
            self.start(root, "fail-new", "2026-07-13T03:00:00+00:00")
            append_event(root, "fail-old", {"kind": "outcome", "status": "fail"})
            append_event(root, "fail-new", {"kind": "outcome", "status": "fail"})
            self.assertEqual(resolve_run_selector(root, "latest-fail"), "fail-new")
        finally:
            holder.cleanup()

    def test_passthrough_and_no_match_error(self) -> None:
        holder, root = self.repo()
        try:
            self.assertEqual(resolve_run_selector(root, "explicit-id"), "explicit-id")
            with self.assertRaisesRegex(ValueError, "no run matches selector 'latest-due'"):
                resolve_run_selector(root, "latest-due")
        finally:
            holder.cleanup()

    def test_reserved_run_start_is_rejected_and_doctor_reports_legacy_id(self) -> None:
        holder, root = self.repo()
        try:
            with self.assertRaisesRegex(ValueError, "reserved as a selector"):
                append_event(root, "latest", {"kind": "run-start"})
            path = root / agent_root("state", "journal", "latest.jsonl")
            path.write_text(json.dumps({"kind": "run-start"}) + "\n", encoding="utf-8")
            result = inspect(root)
            self.assertEqual(result["reserved_run_ids"], ["latest"])
            self.assertFalse(result["ok"])
        finally:
            holder.cleanup()

    def test_hook_explicit_reserved_run_id_is_rejected(self) -> None:
        holder, root = self.repo()
        try:
            result = handle(normalize_codex({"hook_event_name": "SessionStart", "cwd": str(root), "run_id": "latest"}))
            self.assertIn("reserved as a selector", result.get("error", ""))
        finally:
            holder.cleanup()


if __name__ == "__main__":
    unittest.main()
