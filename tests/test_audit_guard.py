from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "utils/audit_guard.py"
INSTALL = ROOT / "utils/install-dev-hooks.sh"


def run(cmd: list[str], cwd: Path, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, input=input_text, text=True, capture_output=True, check=False)


class AuditGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        run(["git", "init"], self.repo)
        run(["git", "config", "user.name", "Test User"], self.repo)
        run(["git", "config", "user.email", "test@example.com"], self.repo)

        (self.repo / "docs").mkdir()
        (self.repo / "utils").mkdir()
        (self.repo / "docs" / "audit-log.md").write_text("# Audit Log\n\n", encoding="utf-8")
        (self.repo / "docs" / "notes.md").write_text("notes\n", encoding="utf-8")
        (self.repo / "utils" / "sample.py").write_text("print('base')\n", encoding="utf-8")
        run(["git", "add", "."], self.repo)
        run(["git", "commit", "-m", "base"], self.repo)
        self.base = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pre_push_rejects_monitored_change_without_audit_log(self) -> None:
        (self.repo / "utils" / "sample.py").write_text("print('changed')\n", encoding="utf-8")
        run(["git", "add", "utils/sample.py"], self.repo)
        run(["git", "commit", "-m", "touch utils"], self.repo)
        head = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()

        result = run(
            ["python3", str(GUARD), "--repo", str(self.repo)],
            self.repo,
            input_text=f"refs/heads/main {head} refs/heads/main {self.base}\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(self.base, result.stderr)
        self.assertIn("docs/audit-log.md", result.stderr)

    def test_docs_only_change_is_exempt(self) -> None:
        (self.repo / "docs" / "notes.md").write_text("notes updated\n", encoding="utf-8")
        run(["git", "add", "docs/notes.md"], self.repo)
        run(["git", "commit", "-m", "docs only"], self.repo)
        head = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()

        result = run(
            ["python3", str(GUARD), "--repo", str(self.repo)],
            self.repo,
            input_text=f"refs/heads/main {head} refs/heads/main {self.base}\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_script_writes_pre_push_hook(self) -> None:
        result = run(["bash", str(INSTALL)], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        hook = self.repo / ".git" / "hooks" / "pre-push"
        self.assertTrue(hook.is_file())
        self.assertIn("utils/audit_guard.py", hook.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
