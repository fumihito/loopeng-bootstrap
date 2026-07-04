from __future__ import annotations

import subprocess
import tempfile
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "utils/completion_protocol_lint.py"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


class CompletionProtocolLintTests(unittest.TestCase):
    def test_protocol_block_is_near_top(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8").splitlines()
        begin_line = next(index + 1 for index, line in enumerate(agents) if line.strip() == "<!-- completion-protocol:begin -->")
        self.assertLessEqual(begin_line, 30)

    def test_protocol_lint_passes_on_repo_root(self) -> None:
        result = run([sys.executable, str(LINT), "--root", str(ROOT)], ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("same completion protocol block", result.stdout)

    def test_protocol_lint_flags_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
            claude = agents.replace(
                "4. 完了宣言に record の出力(または audit 行)を含める。",
                "4. 完了宣言に record の出力だけを含める。",
            )
            (repo / "AGENTS.md").write_text(agents, encoding="utf-8")
            (repo / "CLAUDE.md").write_text(claude, encoding="utf-8")

            result = run([sys.executable, str(LINT), "--root", str(repo)], repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("diverge", result.stderr)


if __name__ == "__main__":
    unittest.main()
