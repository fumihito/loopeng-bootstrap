from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from loopeng.okf.apply import apply_report


REPORT_DOCUMENT = """---
type: "Concept"
title: "Example"
description: "Example concept"
tags: ["example"]
timestamp: "2026-07-10T00:00:00Z"
status: "active"
sensitivity: "internal"
authority: "test"
confidence: "1.0"
---

# Summary
Example
"""

VALID_REPORTS = [
    {"operations": [{"action": "UPSERT", "concept_id": "concepts/example-1", "document": REPORT_DOCUMENT}]},
    {"operations": [{"action": "UPSERT", "concept_id": "concepts/example-2", "document": REPORT_DOCUMENT}]},
    {"operations": [{"action": "DELETE", "concept_id": "concepts/example-3"}]},
    {
        "operations": [
            {"action": "UPSERT", "concept_id": "concepts/example-4", "document": REPORT_DOCUMENT},
            {"action": "DELETE", "concept_id": "concepts/example-5"},
        ]
    },
    {"operations": [{"action": "UPSERT", "concept_id": "concepts/example-6", "document": REPORT_DOCUMENT}]},
]

INVALID_REPORTS = [
    {"operations": [{"action": "PATCH", "concept_id": "concepts/bad", "document": REPORT_DOCUMENT}]},
    {"operations": [{"action": "UPSERT", "concept_id": "", "document": REPORT_DOCUMENT}]},
    {"operations": [{"action": "UPSERT", "concept_id": "concepts/bad", "document": 1}]},
    {"operations": "not-a-list"},
    {"not_operations": []},
]


def make_bundle(root: Path) -> Path:
    bundle = root / "llmwiki"
    bundle.mkdir()
    (bundle / "index.md").write_text("# llmwiki\n", encoding="utf-8")
    (bundle / "log.md").write_text("# log\n", encoding="utf-8")
    return bundle


class OkfApplyTests(unittest.TestCase):
    def test_apply_accepts_golden_reports(self) -> None:
        for index, payload in enumerate(VALID_REPORTS, start=1):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                bundle = make_bundle(root)
                report = root / f"valid-{index}.json"
                report.write_text(json.dumps(payload), encoding="utf-8")

                result = apply_report(bundle, report, root / "backups")
                self.assertTrue(result["ok"])
                self.assertIn("applied", (bundle / "log.md").read_text(encoding="utf-8"))

    def test_apply_rejects_golden_reports_without_writing_bundle(self) -> None:
        for index, payload in enumerate(INVALID_REPORTS, start=1):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                bundle = make_bundle(root)
                before = {path.relative_to(bundle): path.read_text(encoding="utf-8") for path in bundle.rglob("*.md")}
                report = root / f"invalid-{index}.json"
                report.write_text(json.dumps(payload), encoding="utf-8")

                result = apply_report(bundle, report, root / "backups")
                self.assertFalse(result["ok"])
                after = {path.relative_to(bundle): path.read_text(encoding="utf-8") for path in bundle.rglob("*.md")}
                self.assertEqual(before, after)
