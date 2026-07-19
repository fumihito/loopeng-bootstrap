from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from loopeng.hooks import handler
from loopeng.hooks.codex import normalize
from loopeng.audit.policy import HARD_BLOCKS
from loopeng.journal import sanitize_event
from loopeng.trace import render, record_post, record_pre


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TraceTests(unittest.TestCase):
    def test_a1_hook_records_trace_without_changing_journal_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            started = handler.handle(normalize({"hook_event_name": "SessionStart", "cwd": str(repo), "session_id": "a1"}))
            run_id = started["run_id"]
            event = {"hook_event_name": "PreToolUse", "cwd": str(repo), "run_id": run_id, "tool_name": "Read", "tool_input": {"path": "notes.md"}}
            handler.handle(normalize(event))
            handler.handle(normalize({**event, "hook_event_name": "PostToolUse", "tool_response": "contents"}))
            journal = repo / ".agent-loop/state/journal" / f"{run_id}.jsonl"
            before = [item["kind"] for item in read_jsonl(journal)]
            self.assertEqual([item["phase"] for item in read_jsonl(repo / ".agent-loop/state/trace" / f"{run_id}.jsonl")], ["pre", "post"])
            self.assertEqual(before, ["run-start", "mutation"])

    def test_a2_pairing_id_heuristic_and_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, run = Path(td), "a2"
            record_pre(repo, run, "codex", {"tool_name": "Read", "tool_input": {}, "tool_use_id": "call-1"})
            record_post(repo, run, "codex", {"tool_name": "Read", "tool_response": {}, "tool_use_id": "call-1"})
            record_pre(repo, run, "codex", {"tool_name": "Grep", "tool_input": {}})
            record_post(repo, run, "codex", {"tool_name": "Grep", "tool_response": {}})
            record_pre(repo, run, "codex", {"tool_name": "Glob", "tool_input": {}})
            record_pre(repo, run, "codex", {"tool_name": "Glob", "tool_input": {}})
            record_post(repo, run, "codex", {"tool_name": "Glob", "tool_response": {}})
            records = read_jsonl(repo / ".agent-loop/state/trace" / f"{run}.jsonl")
            self.assertEqual(records[1]["pairing"], "id")
            self.assertGreater(records[1]["duration_ms"], 0)
            self.assertEqual(records[3]["pairing"], "heuristic")
            self.assertEqual(records[-1]["pairing"], "ambiguous")
            self.assertIsNone(records[-1]["duration_ms"])

    def test_a3_sanitizes_before_excerpt_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, run = Path(td), "a3"
            value = {"command": "echo token=abc123"}
            record_pre(repo, run, "codex", {"tool_name": "Bash", "tool_input": value})
            record = read_jsonl(repo / ".agent-loop/state/trace" / f"{run}.jsonl")[0]
            sanitized = sanitize_event({"value": value})["value"]
            expected = json.dumps(sanitized, ensure_ascii=False, sort_keys=True)
            self.assertNotIn("abc123", record["input_excerpt"])
            self.assertIn("<redacted>", record["input_excerpt"])
            self.assertEqual(record["input_digest"], "sha256:" + hashlib.sha256(expected.encode()).hexdigest())

    def test_a4_trace_failure_is_fail_open(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            with mock.patch("loopeng.hooks.handler.record_pre", side_effect=OSError("read-only")):
                allowed = handler.handle(normalize({"hook_event_name": "PreToolUse", "cwd": str(repo), "tool_input": {"command": "echo ok"}}))
            self.assertNotIn("permissionDecision", allowed["response"].get("hookSpecificOutput", {}))
            with mock.patch("loopeng.hooks.handler.render_trace", side_effect=OSError("read-only")):
                stopped = handler.handle(normalize({"hook_event_name": "Stop", "cwd": str(repo), "run_id": "a4"}))
            self.assertEqual(stopped["response"], {"continue": True})

    def test_a5_render_is_deterministic_and_keeps_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, run = Path(td), "a5"
            record_pre(repo, run, "codex", {"tool_name": "Read", "tool_input": {"path": "a.md"}})
            record_post(repo, run, "codex", {"tool_name": "Read", "tool_response": "exact response"})
            first = render(repo, run_id=run)
            first_bytes = [path.read_bytes() for path in first]
            second = render(repo, run_id=run)
            self.assertEqual(first_bytes, [path.read_bytes() for path in second])
            body = first[0].read_text(encoding="utf-8")
            self.assertTrue(all(section in body for section in ("## Summary", "## Timeline", "## Denied", "## Call details", "## Provenance")))
            self.assertIn("exact response", body)

    def test_a6_codex_matchers_are_wildcards(self) -> None:
        config = json.loads((Path(__file__).parents[1] / "adapters/codex/.codex/hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(config["hooks"]["PreToolUse"][0]["matcher"], "*")
        self.assertEqual(config["hooks"]["PostToolUse"][0]["matcher"], "*")

    def test_a7_deny_has_trace_record_and_unchanged_response(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            result = handler.handle(normalize({"hook_event_name": "PreToolUse", "cwd": str(repo), "run_id": "a7", "tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}))
            self.assertEqual(result["response"]["hookSpecificOutput"]["permissionDecision"], "deny")
            records = read_jsonl(repo / ".agent-loop/state/trace/a7.jsonl")
            self.assertEqual(records[-1]["phase"], "deny")
            self.assertEqual(records[-1]["deny_reason"], HARD_BLOCKS["destructive_command"])


if __name__ == "__main__":
    unittest.main()
