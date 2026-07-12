from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from loopeng.okf.curate import curate
from loopeng.okf.query import query_bundle


class AutonomousMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        bundle = self.repo / "llmwiki"
        for namespace in ("concepts", "decisions", "constraints", "failure-patterns", "evaluation-rules", "recovery-patterns", "runbooks", "references"):
            (bundle / namespace).mkdir(parents=True)
        (bundle / "index.md").write_text("---\ntitle: test\n---\n# test\n", encoding="utf-8")
        (bundle / "log.md").write_text("# log\n", encoding="utf-8")
        self.learning = self.repo / ".agent-loop/state/learning"
        self.learning.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def add_learning(self, number: int, kind: str = "Failure Pattern") -> None:
        payload = {"type": kind, "title": f"candidate {number}", "summary": "observed recovery", "tags": ["failure", "recovery"], "source_run_id": "r1"}
        (self.learning / f"candidate-{number}.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_autonomous_scope_limit_tier_and_idempotence(self) -> None:
        for number in range(4):
            self.add_learning(number)
        self.add_learning(9, "Decision")
        first = curate(self.repo, "r1", top=10)
        self.assertEqual(len(first["applied"]), 3)
        self.assertEqual(len(first["pending"]), 2)
        provisional = query_bundle(self.repo / "llmwiki", tier="provisional")
        self.assertEqual(len(provisional), 3)
        self.assertTrue(all(item["label"] == "[provisional]" for item in provisional))
        self.assertEqual(curate(self.repo, "r1")["applied"], [])
        self.assertEqual(len(query_bundle(self.repo / "llmwiki", tier="established")), 0)

