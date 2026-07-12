from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from loopeng.memory_stats import collect_stats
from loopeng.okf.apply import apply_report
from loopeng.okf.schema import validate_bundle


DOC = '''---
type: "Concept"
title: "Example"
description: "Example"
tags: [example]
timestamp: "2026-01-01"
status: "active"
sensitivity: "internal"
authority: "test"
confidence: "1"
---

Body
'''


def bundle(root: Path) -> Path:
    path = root / "llmwiki"
    path.mkdir()
    (path / "index.md").write_text("# index\n", encoding="utf-8")
    (path / "log.md").write_text("# log\n", encoding="utf-8")
    return path


class MemoryStatsTests(unittest.TestCase):
    def test_apply_writes_one_v1_entry_per_operation_and_validate_checks_it(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, target = Path(td), bundle(Path(td))
            report = root / "report.json"
            report.write_text(json.dumps({"role": "codex", "run_id": "r1", "operations": [
                {"action": "UPSERT", "proposal_id": "p1", "concept_id": "concepts/a", "document": DOC},
                {"action": "UPSERT", "proposal_id": "p2", "concept_id": "concepts/b", "document": DOC},
            ]}), encoding="utf-8")
            self.assertTrue(apply_report(target, report, root / "backups")["ok"])
            rows = [json.loads(line) for line in (target / "log.jsonl").read_text().splitlines()]
            self.assertEqual([row["proposal_id"] for row in rows], ["p1", "p2"])
            self.assertTrue(validate_bundle(target)["ok"])
            (target / "log.jsonl").write_text('{"v": 2}\n', encoding="utf-8")
            self.assertFalse(validate_bundle(target)["ok"])

    def test_apply_failure_rolls_back_json_log(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, target = Path(td), bundle(Path(td))
            report = root / "report.json"
            report.write_text(json.dumps({"operations": [{"action": "UPSERT", "proposal_id": "p1", "concept_id": "concepts/a", "document": DOC}]}), encoding="utf-8")
            with patch("loopeng.okf.apply.reindex_bundle", side_effect=OSError("injected")):
                result = apply_report(target, report, root / "backups")
            self.assertFalse(result["ok"])
            self.assertFalse((target / "log.jsonl").exists())
            self.assertFalse((target / "concepts/a.md").exists())

    def test_stats_uses_log_only_and_includes_cutoff_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, target = Path(td), bundle(Path(td))
            rows = [
                {"v": 1, "ts": "2026-07-11T12:00:00Z", "action": "UPSERT", "namespace": "failure-patterns", "type": "Failure Pattern", "tier": "provisional", "author": "codex"},
                {"v": 1, "ts": "2026-07-10T11:59:59Z", "action": "DEPRECATE", "namespace": "references", "type": "Reference", "tier": "established", "author": "hito"},
            ]
            (target / "log.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            stats = collect_stats(root, target, now="2026-07-12T12:00:00Z")
            self.assertEqual(stats["windows"]["1d"]["ops"], 1)
            self.assertEqual(stats["windows"]["3d"]["ops"], 2)
            self.assertEqual(stats["windows"]["3d"]["by"]["action"]["DEPRECATE"], 1)


if __name__ == "__main__":
    unittest.main()
