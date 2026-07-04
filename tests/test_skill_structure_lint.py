from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "utils/skill_structure_lint.py"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


class SkillStructureLintTests(unittest.TestCase):
    def test_lint_passes_on_repo_root(self) -> None:
        result = run([sys.executable, str(LINT), "--root", str(ROOT)], ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("passed structure lint", result.stdout)

    def test_lint_flags_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill_dir = root / "adapters/shared/skills/frame-sample"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: frame-sample
description: \"Test frame for linting. Use when a sample is enough. The point is to stay concise.\"
user-invocable: true
---

## Purpose

Test frame.
""",
                encoding="utf-8",
            )

            result = run([sys.executable, str(LINT), "--root", str(root)], root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required section", result.stdout)


if __name__ == "__main__":
    unittest.main()
