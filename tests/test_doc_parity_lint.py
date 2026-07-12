from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from loopeng.journal import EVENT_KINDS


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("doc_parity_lint_under_test", ROOT / "utils/doc_parity_lint.py")
assert SPEC is not None and SPEC.loader is not None
lint_module = importlib.util.module_from_spec(SPEC)
sys.modules["doc_parity_lint_under_test"] = lint_module
SPEC.loader.exec_module(lint_module)


class DocParityLintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "docs").mkdir()
        (self.root / "utils").mkdir()
        (self.root / "loopeng").mkdir()
        (self.root / "docs/doc-map.json").write_text(json.dumps({
            "cli_subcommands": ["README.md", "README.ja.md"],
            "review_views": ["README.md", "README.ja.md", "docs/RUN_REPORT.md"],
            "event_kinds": ["docs/RUN_REPORT.md"],
            "hook_platforms": ["docs/INSTALL.md", "docs/ARCHITECTURE.md"],
            "mode_words": ["AGENTS.md", "CLAUDE.md"],
        }), encoding="utf-8")
        (self.root / "docs/INSTALL.md").write_text("Claude Code Codex docs/ARCHITECTURE.md\n", encoding="utf-8")
        (self.root / "docs/ARCHITECTURE.md").write_text("Claude Code Codex\n", encoding="utf-8")
        (self.root / "docs/RUN_REPORT.md").write_text("status dag " + " ".join(EVENT_KINDS), encoding="utf-8")
        readme = "status dag review: route: `docs/INSTALL.md`\n<!-- ongoing-start -->\nokf query\n<!-- ongoing-end -->\n"
        (self.root / "README.md").write_text(readme, encoding="utf-8")
        (self.root / "README.ja.md").write_text(readme, encoding="utf-8")
        (self.root / "AGENTS.md").write_text("review: route:\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("review: route:\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_all_five_checks_pass_on_fixture(self) -> None:
        with patch.object(lint_module, "_parser_surface", return_value=(["status"], ["dag"])):
            self.assertEqual(lint_module.lint(self.root), [])

    def test_cli_surface_negative(self) -> None:
        (self.root / "README.ja.md").write_text("", encoding="utf-8")
        with patch.object(lint_module, "_parser_surface", return_value=(["status"], ["dag"])):
            self.assertTrue(any("1 cli surface" in item for item in lint_module.lint(self.root)))

    def test_event_contract_negative(self) -> None:
        (self.root / "docs/RUN_REPORT.md").write_text("status dag", encoding="utf-8")
        with patch.object(lint_module, "_parser_surface", return_value=(["status"], ["dag"])):
            self.assertTrue(any("2 event contract" in item for item in lint_module.lint(self.root)))

    def test_ongoing_implemented_feature_negative(self) -> None:
        (self.root / "README.md").write_text("status dag review:\n<!-- ongoing-start -->\nstatus\n<!-- ongoing-end -->", encoding="utf-8")
        with patch.object(lint_module, "_parser_surface", return_value=(["status"], ["dag"])):
            self.assertTrue(any("3 ongoing status" in item for item in lint_module.lint(self.root)))

    def test_reference_path_negative(self) -> None:
        (self.root / "README.md").write_text("status dag review: route: `docs/missing.md`\n<!-- ongoing-start -->okf query<!-- ongoing-end -->", encoding="utf-8")
        with patch.object(lint_module, "_parser_surface", return_value=(["status"], ["dag"])):
            self.assertTrue(any("4 reference path" in item for item in lint_module.lint(self.root)))

    def test_japanese_body_parity_negative(self) -> None:
        (self.root / "README.ja.md").write_text("status\n<!-- ongoing-start -->okf query<!-- ongoing-end -->", encoding="utf-8")
        with patch.object(lint_module, "_parser_surface", return_value=(["status"], ["dag"])):
            self.assertTrue(any("5 en-ja parity" in item for item in lint_module.lint(self.root)))

    def test_production_event_dicts_use_declared_kinds(self) -> None:
        for path in (ROOT / "loopeng").rglob("*.py"):
            self.assertNotIn('"kind": "', path.read_text(encoding="utf-8"), str(path))


if __name__ == "__main__":
    unittest.main()
