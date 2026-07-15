from __future__ import annotations

import unittest
from pathlib import Path

from utils.distribution_lint import lint


ROOT = Path(__file__).resolve().parents[1]


class DistributionLintTests(unittest.TestCase):
    def test_full_plan_covers_every_loopeng_module(self) -> None:
        self.assertEqual(lint(ROOT), [])

    def test_development_only_utilities_are_not_runtime_payload(self) -> None:
        import utils.distribution_lint as distribution_lint

        original = distribution_lint.DEV_ONLY_PREFIXES
        try:
            distribution_lint.DEV_ONLY_PREFIXES = ("loopeng.py",)
            errors = distribution_lint.lint(ROOT)
        finally:
            distribution_lint.DEV_ONLY_PREFIXES = original
        self.assertTrue(any("development-only path is distributed" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
