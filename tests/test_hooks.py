from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from loopeng.hooks import handler
from loopeng.hooks.claude_code import normalize as normalize_claude
from loopeng.hooks.codex import normalize as normalize_codex
from loopeng.hooks.events import EventKind


ROOT = Path(__file__).resolve().parents[1]


class HookTests(unittest.TestCase):
    def test_adapters_agree_on_representative_events(self) -> None:
        for name, expected in (("SessionStart", EventKind.SESSION_START), ("UserPromptSubmit", EventKind.PROMPT_SUBMIT), ("PreToolUse", EventKind.PRE_TOOL), ("PostToolUse", EventKind.POST_TOOL), ("Stop", EventKind.RUN_STOP)):
            codex = {"hook_event_name": name, "cwd": str(ROOT), "tool_name": "Bash"}
            claude = {**codex}
            self.assertEqual(normalize_codex(codex).kind, expected)
            self.assertEqual(normalize_claude(claude).kind, expected)

    def test_lifecycle_journal_handoff_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            state = repo / ".agent-loop/state"
            state.mkdir(parents=True)
            (state / "handoff.json").write_text(json.dumps({"summary": "resume this work"}), encoding="utf-8")
            event = normalize_codex({"hook_event_name": "SessionStart", "cwd": str(repo), "session_id": "s"})
            started = handler.handle(event)
            self.assertTrue(started["run_id"])
            self.assertIn("additionalContext", json.dumps(started))
            journal = next((state / "journal").glob("*.jsonl"))
            self.assertIn('"kind": "run-start"', journal.read_text(encoding="utf-8"))
            handler.handle(normalize_codex({"hook_event_name": "PostToolUse", "cwd": str(repo), "run_id": started["run_id"], "tool_name": "Bash", "tool_input": {"command": "echo token=secret"}}))
            post_body = journal.read_text(encoding="utf-8")
            self.assertIn('"kind": "command"', post_body)
            self.assertIn("<redacted>", post_body)
            stopped = handler.handle(normalize_codex({"hook_event_name": "Stop", "cwd": str(repo), "run_id": started["run_id"]}))
            self.assertEqual(stopped["response"], {"continue": True})
            self.assertTrue((state / "reports" / f"{started['run_id']}.md").is_file())

    def test_pre_tool_only_blocks_declared_hard_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            denied = handler.handle(normalize_codex({"hook_event_name": "PreToolUse", "cwd": str(repo), "tool_input": {"command": "rm -rf /"}}))
            self.assertEqual(denied["response"]["hookSpecificOutput"]["permissionDecision"], "deny")
            allowed = handler.handle(normalize_codex({"hook_event_name": "PreToolUse", "cwd": str(repo), "tool_input": {"command": "echo hello"}}))
            self.assertEqual(allowed["response"]["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_run_stop_is_fail_open_when_state_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            path = repo / ".agent-loop/state/active-run.json"
            path.parent.mkdir(parents=True)
            path.write_text("{broken", encoding="utf-8")
            result = handler.handle(normalize_codex({"hook_event_name": "Stop", "cwd": str(repo), "run_id": "broken-state"}))
            self.assertEqual(result["response"], {"continue": True})
            self.assertNotIn("block", json.dumps(result).lower())

    def test_cli_uses_requested_platform(self) -> None:
        proc = subprocess.run([sys.executable, "-m", "loopeng", "hook", "claude-code"], input=json.dumps({"hook_event_name": "Stop", "cwd": str(ROOT), "run_id": "cli"}), text=True, capture_output=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn('"decision": "block"', proc.stdout)


if __name__ == "__main__":
    unittest.main()
