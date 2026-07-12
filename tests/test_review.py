from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from loopeng._paths import agent_root
from loopeng.okf.schema import validate_document_text
from loopeng.review import render_review


def sidecar(root: Path, run_id: str, *, check: str | None = None, ended: str | None = None) -> None:
    report_dir = root / agent_root("state", "reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "agent": "test",
        "goal": run_id,
        "started_at": ended or "2026-07-12T00:00:00+00:00",
        "ended_at": ended or "2026-07-12T00:01:00+00:00",
        "alerts": ([{"check_id": check, "severity": "warn", "declared": True}] if check else []),
        "undeclared_critical": False,
        "memory": {"applied": 1, "rejected": 0},
        "handoff_written": True,
        "schema": 1,
    }
    (report_dir / f"{run_id}.json").write_text(json.dumps(report), encoding="utf-8")


class ReviewTests(unittest.TestCase):
    def test_results_are_sidecar_only_and_limited(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for index in range(6):
                sidecar(root, f"run-{index}", ended=f"2026-07-12T00:0{index}:00+00:00")
            text = render_review(root)
            self.assertIn("Scope: last 5 of 5 runs with sidecar", text)
            self.assertIn("run-5", text)
            self.assertNotIn("run-0", text)

    def test_recurring_threshold_is_three_runs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for index in range(5):
                sidecar(root, f"run-{index}", check="budget_exceeded" if index < 3 else None, ended=f"2026-07-12T00:0{index}:00+00:00")
            self.assertIn("[RECURRING] budget_exceeded", render_review(root, 5))
            (root / agent_root("state", "reports") / "run-2.json").unlink()
            self.assertNotIn("[RECURRING] budget_exceeded", render_review(root, 5))

    def test_premises_markers_and_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            decisions = root / "llmwiki" / "decisions"
            constraints = root / "llmwiki" / "constraints"
            decisions.mkdir(parents=True)
            constraints.mkdir(parents=True)
            base = '''---
type: "Decision"
title: "{title}"
description: "test"
tags: [{tags}]
timestamp: "2026-01-01T00:00:00Z"
status: "{status}"
sensitivity: "internal"
authority: "test"
confidence: "1.0"
{extra}---

# Invalidation
If the observed condition changes.
'''
            (decisions / "due.md").write_text(base.format(title="Due", tags='"x"', status="active", extra='review_after: "2020-01-01"\n'), encoding="utf-8")
            (decisions / "pending.md").write_text(base.format(title="Pending", tags='"pending-decision"', status="active", extra=""), encoding="utf-8")
            (constraints / "deprecated.md").write_text(base.format(title="Old", tags='"x"', status="deprecated", extra=""), encoding="utf-8")
            text = render_review(root, section="premises")
            self.assertIn("[DUE]", text)
            self.assertIn("[PENDING]", text)
            self.assertIn("If the observed condition changes.", text)
            self.assertNotIn("deprecated", text)

    def test_review_after_validation(self) -> None:
        valid = '''---
type: "Decision"
title: "D"
description: "d"
tags: ["x"]
timestamp: "2026-01-01"
status: "active"
sensitivity: "internal"
authority: "test"
confidence: "1.0"
review_after: "2026-07-01"
---
# D
'''
        invalid = valid.replace('"2026-07-01"', '"not-a-date"')
        self.assertEqual(validate_document_text(valid), [])
        self.assertTrue(any("review_after" in error for error in validate_document_text(invalid)))

    def test_audit_writes_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            journal = root / agent_root("state", "journal")
            journal.mkdir(parents=True)
            events = [
                {"kind": "run-start", "agent": "codex", "goal": "test", "timestamp": "2026-07-12T00:00:00+00:00"},
                {"kind": "run-end", "timestamp": "2026-07-12T00:01:00+00:00"},
            ]
            (journal / "r1.jsonl").write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")
            subprocess.run([sys.executable, "-m", "loopeng", "audit", "run", "--run", "r1", "--repo", str(root)], check=True, capture_output=True, text=True)
            payload = json.loads((root / agent_root("state", "reports") / "r1.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], 1)
            self.assertEqual(payload["goal"], "test")

