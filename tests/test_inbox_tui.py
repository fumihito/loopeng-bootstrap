from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from loopeng.inbox_model import ACTION_TABLE, actions_for, execute, generate_packet, interactive, packet_detail_lines
from loopeng.inbox_tui import _available_label
from loopeng.review_request import build_request
from loopeng.okf.index import reindex_bundle


def _document(concept: str, tier: str = "provisional") -> tuple[str, str]:
    namespace, name = concept.split("/", 1)
    type_name = {"failure-patterns": "Failure Pattern", "decisions": "Decision"}[namespace]
    text = "---\n" + "\n".join((
        f'type: "{type_name}"', f'title: "{name}"', f'description: "{name}"', "tags: []",
        'timestamp: "2026-07-13T00:00:00Z"', "status: active", "sensitivity: internal",
        'authority: "test"', "confidence: 0.7", f"tier: {tier}", 'space: "project"',
    )) + "\n---\n\n# Summary\n\nbody\n"
    return namespace, text


class InboxModelTests(unittest.TestCase):
    def repo(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        holder = tempfile.TemporaryDirectory()
        root = Path(holder.name)
        for namespace in ("concepts", "decisions", "constraints", "failure-patterns", "evaluation-rules", "recovery-patterns", "runbooks", "references"):
            (root / "llmwiki" / namespace).mkdir(parents=True)
        reindex_bundle(root / "llmwiki")
        return holder, root

    def test_action_table_and_external_review_have_no_resolve_action(self) -> None:
        self.assertEqual(actions_for({"kind": "provisional"}), ACTION_TABLE["provisional"])
        self.assertNotIn("accept", actions_for({"kind": "external-review"}))
        self.assertNotIn("resolve", actions_for({"kind": "external-review"}))

    def test_marked_action_label_flattens_action_tuples(self) -> None:
        self.assertEqual(_available_label([{"kind": "provisional"}], {0}), "detail,establish,skip")

    def test_reject_requires_reason_and_interactive_records_session(self) -> None:
        holder, root = self.repo()
        try:
            draft_root = root / ".agent-loop/state/memory-drafts"
            draft_root.mkdir(parents=True)
            draft = {"draft_id": "d1", "operations": [{"action": "UPSERT", "concept_id": "decisions/d1", "document": _document("decisions/d1", "established")[1]}]}
            (draft_root / "d1.json").write_text(json.dumps(draft), encoding="utf-8")
            item = {"kind": "draft", "target": "d1", "path": ".agent-loop/state/memory-drafts/d1.json"}
            result = execute(root, item, "reject", "tui-test", "")
            self.assertTrue(result["cancelled"])
            output = io.StringIO()
            interactive(root, io.StringIO("1\nreject\n\nq\nn\n"), output)
            journal = next((root / ".agent-loop/state/journal").glob("tui-*.jsonl"))
            text = journal.read_text(encoding="utf-8")
            self.assertIn('"kind": "run-start"', text)
            self.assertIn('"kind": "run-end"', text)
            self.assertIn("Cancelled", output.getvalue())
        finally:
            holder.cleanup()

    def test_bulk_establish_rejects_mixed_kinds(self) -> None:
        holder, root = self.repo()
        try:
            result = execute(root, [{"kind": "provisional", "target": "llmwiki/decisions/a.md"}, {"kind": "draft", "target": "d"}], "establish", "tui-test")
            self.assertFalse(result["ok"])
            self.assertIn("provisional", result["error"])
        finally:
            holder.cleanup()

    def test_external_request_delegates_and_does_not_accept(self) -> None:
        holder, root = self.repo()
        try:
            with mock.patch("loopeng.inbox_model.build_request", return_value="request") as request:
                result = execute(root, {"kind": "external-review", "target": "run-1"}, "request", "tui-test")
            request.assert_called_once_with(root, "run-1")
            self.assertEqual(result["request"], "request")
            self.assertNotIn("accepted", result)
        finally:
            holder.cleanup()

    def test_missing_packet_is_not_reported_as_an_existing_path(self) -> None:
        holder, root = self.repo()
        try:
            request = build_request(root, "missing-run")
            self.assertIn("Review packet: unavailable", request)
            self.assertNotIn("review-packets/missing-run/manifest.json", request)
        finally:
            holder.cleanup()

    def test_packet_detail_reads_manifest_listed_files(self) -> None:
        holder, root = self.repo()
        try:
            packet = root / ".agent-loop/state/review-packets/r1"
            packet.mkdir(parents=True)
            (packet / "journal.json").write_text("journal content\n", encoding="utf-8")
            (packet / "manifest.json").write_text(json.dumps({"run_id": "r1", "files": ["journal.json"]}), encoding="utf-8")
            lines = packet_detail_lines(packet)
            self.assertIn("===== journal.json =====", lines)
            self.assertIn("journal content", lines)
        finally:
            holder.cleanup()

    def test_generate_packet_delegates_to_audit_export(self) -> None:
        holder, root = self.repo()
        try:
            expected = root / "packet"
            with mock.patch("loopeng.inbox_model.export_packet", return_value=expected) as export:
                self.assertEqual(generate_packet(root, "run-1"), expected)
            export.assert_called_once_with(root.resolve(), "run-1")
        finally:
            holder.cleanup()

    def test_tui_keyboard_interrupt_closes_without_traceback(self) -> None:
        holder, root = self.repo()
        try:
            from loopeng.cli import main
            output = mock.patch("builtins.print")
            with mock.patch("loopeng.cli.sys.stdin.isatty", return_value=True), mock.patch("loopeng.cli.sys.stdout.isatty", return_value=True), mock.patch("loopeng.inbox_tui.run", side_effect=KeyboardInterrupt), mock.patch("builtins.input", return_value="n"), output as printed:
                self.assertEqual(main(["inbox", "--tui", "--repo", str(root)]), 0)
            self.assertTrue(any("Inbox TUI interrupted; session closed." in str(call) for call in printed.call_args_list))
        finally:
            holder.cleanup()


if __name__ == "__main__":
    unittest.main()
