import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
SCRIPT = KIT / "utils" / "check_publish_safety.py"


class PublishSafetyScriptTests(unittest.TestCase):
    def run_script(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root)],
            check=False,
            text=True,
            capture_output=True,
            timeout=30,
        )

    def test_clean_tree_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "notes.md").write_text("Public project notes only.\n", encoding="utf-8")
            result = self.run_script(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("OK: no obvious credentials", result.stdout)

    def test_detects_sensitive_file_names_and_values(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            token = "".join(["Abcd", "1234", "!", "Efgh", "5678"])
            (root / ".env").write_text("API_KEY=" + token + "\n", encoding="utf-8")
            (root / "safe.md").write_text("This file is fine.\n", encoding="utf-8")
            result = self.run_script(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(".env", result.stdout)
            self.assertIn("sensitive assignment", result.stdout)
            self.assertIn("suspicious file name", result.stdout)


if __name__ == "__main__":
    unittest.main()
