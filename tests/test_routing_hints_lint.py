from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from utils.routing_hints_lint import lint


ROOT = Path(__file__).resolve().parents[1]


class RoutingHintsLintTests(unittest.TestCase):
    def test_all_frame_skills_have_routing_hints(self) -> None:
        self.assertEqual(lint(ROOT), [])

    def test_missing_routing_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "adapters/shared/skills/frame-demo").mkdir(parents=True)
            self.assertEqual(lint(root), ["frame-demo: missing routing.md"])

    def test_wrong_frame_and_missing_block_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "adapters/shared/skills/frame-demo"
            path.mkdir(parents=True)
            (path / "routing.md").write_text(
                """```route-hints-v1\nschema = \"routing-hints/v1\"\nframe = \"frame-other\"\npriority = 101\nsummary = \"demo\"\n[[prefer]]\n""",
                encoding="utf-8",
            )
            errors = lint(root)
            self.assertIn("frame-demo: frame field must be \"frame-demo\"", errors)
            self.assertIn("frame-demo: priority must be between 0 and 100", errors)
            self.assertIn("frame-demo: missing [[signals]] block", errors)
