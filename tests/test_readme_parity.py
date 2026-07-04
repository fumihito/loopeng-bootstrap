import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


class ReadmeParityLintTests(unittest.TestCase):
    def test_readme_heading_parity_passes_for_repo(self):
        proc = subprocess.run(
            [sys.executable, str(KIT / "utils" / "readme_parity_lint.py"), "--root", str(KIT)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("OK: README heading structure matches", proc.stdout)

    def test_readme_heading_parity_detects_structure_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# A\n## B\n", encoding="utf-8")
            (root / "README.ja.md").write_text("# A\n### C\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(KIT / "utils" / "readme_parity_lint.py"), "--root", str(root)],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("heading structure mismatch", proc.stdout)


if __name__ == "__main__":
    unittest.main()
