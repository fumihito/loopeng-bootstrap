from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from loopeng.hooks import handler
from loopeng.hooks.codex import normalize
from loopeng.okf.approval import approve, list_drafts, reject, snooze
from loopeng.okf.draft import make_draft
from loopeng.review import render_review
from loopeng.inbox import collect_inbox


class MemoryApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        for namespace in ("concepts", "decisions", "constraints", "failure-patterns", "evaluation-rules", "recovery-patterns", "runbooks", "references"):
            (self.repo / "llmwiki" / namespace).mkdir(parents=True)
        (self.repo / "llmwiki" / "index.md").write_text("---\ntitle: test\n---\n# test\n", encoding="utf-8")
        (self.repo / "llmwiki" / "log.md").write_text("# log\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def draft(self, concept: str = "decisions/example") -> str:
        path, _ = make_draft(self.repo, "Decision", concept, "Example", ["test"], "# Summary\n\nDraft body.")
        return path.stem

    def test_prompt_is_bounded_and_one_per_session(self) -> None:
        ids = [self.draft(f"decisions/example-{i}") for i in range(6)]
        event = normalize({"hook_event_name": "UserPromptSubmit", "cwd": str(self.repo), "session_id": "s"})
        first = handler.handle(event)
        context = first["response"]["hookSpecificOutput"]["additionalContext"]
        self.assertIn("6 memory drafts await approval", context)
        self.assertIn("... and 1 more", context)
        self.assertEqual(handler.handle(event)["response"], {})
        self.assertTrue(any(event.get("kind") == "approval-request" for event in
                            [json.loads(line) for line in (self.repo / ".agent-loop/state/journal" / f"{first['run_id']}.jsonl").read_text().splitlines()]))

    def test_snooze_and_state_corruption_are_fail_open_without_prompt(self) -> None:
        self.draft()
        snooze(self.repo, "r", 3)
        event = normalize({"hook_event_name": "UserPromptSubmit", "cwd": str(self.repo), "session_id": "s"})
        self.assertNotIn("approval-request", json.dumps(handler.handle(event)))
        self.assertIn("[HELD] memory-approval", render_review(self.repo))
        self.assertIn("memory-approval", "\n".join(item["target"] for item in collect_inbox(self.repo)))
        (self.repo / ".agent-loop/state/approval-snooze.json").unlink()
        (self.repo / ".agent-loop/state/approval-prompt.json").parent.mkdir(parents=True, exist_ok=True)
        (self.repo / ".agent-loop/state/approval-prompt.json").write_text("{broken", encoding="utf-8")
        self.assertNotIn("approval-request", json.dumps(handler.handle(event)))

    def test_approve_and_reject_keep_files_and_record_quote(self) -> None:
        approved = self.draft("decisions/approved")
        rejected = self.draft("decisions/rejected")
        result = approve(self.repo, [approved], 'I explicitly approve this draft', "r")
        self.assertEqual(result["applied"], [approved])
        self.assertTrue((self.repo / ".agent-loop/state/memory-drafts/applied" / f"{approved}.json").is_file())
        reject(self.repo, rejected, "not applicable", "r")
        self.assertTrue((self.repo / ".agent-loop/state/memory-drafts/rejected" / f"{rejected}.json").is_file())
        journal = (self.repo / ".agent-loop/state/journal/r.jsonl").read_text(encoding="utf-8")
        self.assertIn("I explicitly approve this draft", journal)

    def test_quote_is_sanitized_and_partial_all_continues(self) -> None:
        first = self.draft("decisions/partial-a")
        second = self.draft("decisions/partial-b")
        path = self.repo / ".agent-loop/state/memory-drafts" / f"{second}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["operations"][0]["concept_id"] = "not-allowed/partial-b"
        path.write_text(json.dumps(value), encoding="utf-8")
        result = approve(self.repo, [first, second], "approve token=secret", "r")
        self.assertEqual(result["applied"], [first])
        self.assertEqual(result["failed"][0]["id"], second)
        journal = (self.repo / ".agent-loop/state/journal/r.jsonl").read_text(encoding="utf-8")
        self.assertIn("token=<redacted>", journal)

    def test_pending_set_change_allows_next_request(self) -> None:
        first = self.draft("decisions/set-a")
        event = normalize({"hook_event_name": "UserPromptSubmit", "cwd": str(self.repo), "session_id": "s"})
        self.assertIn("memory drafts await approval", json.dumps(handler.handle(event)))
        self.draft("decisions/set-b")
        second = handler.handle(event)
        self.assertIn("memory drafts await approval", json.dumps(second))

    def test_seed_import_is_idempotent(self) -> None:
        source = self.repo / "docs/v0.2-phase1/seed-drafts"
        source.mkdir(parents=True)
        (source / "d-one.json").write_text(json.dumps({"draft_id": "d-one", "operations": []}), encoding="utf-8")
        from loopeng.okf.curate import _import_seed_drafts
        self.assertEqual(_import_seed_drafts(self.repo), ["d-one"])
        self.assertEqual(_import_seed_drafts(self.repo), [])
        self.assertEqual(len(list((self.repo / ".agent-loop/state/memory-drafts").glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
