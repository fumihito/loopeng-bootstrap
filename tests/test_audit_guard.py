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

    def write_audit_log(self, *entries: str) -> None:
        body = "# Audit Log\n\n" + "\n".join(entries)
        if entries:
            body += "\n"
        (self.repo / "docs" / "audit-log.md").write_text(body, encoding="utf-8")

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
        self.assertIn(f"audit entry for parent hash {self.base}", result.stderr)
        self.assertIn("docs/audit-log.md", result.stderr)

    def test_note_line_does_not_satisfy_guard(self) -> None:
        (self.repo / "utils" / "sample.py").write_text("print('changed')\n", encoding="utf-8")
        run(["git", "add", "utils/sample.py"], self.repo)
        run(["git", "commit", "-m", "touch utils"], self.repo)
        head = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()
        self.write_audit_log(
            f"- 2026-07-03 | note {self.base} | supplemental note that must not satisfy the guard."
        )

        result = run(
            ["python3", str(GUARD), "--repo", str(self.repo)],
            self.repo,
            input_text=f"refs/heads/main {head} refs/heads/main {self.base}\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"audit entry for parent hash {self.base}", result.stderr)

    def test_audit_line_satisfies_guard(self) -> None:
        (self.repo / "utils" / "sample.py").write_text("print('changed')\n", encoding="utf-8")
        run(["git", "add", "utils/sample.py"], self.repo)
        run(["git", "commit", "-m", "touch utils"], self.repo)
        head = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()
        self.write_audit_log(
            f"- 2026-07-03 | audit {self.base} | canonical audit record for the audited snapshot."
        )

        result = run(
            ["python3", str(GUARD), "--repo", str(self.repo)],
            self.repo,
            input_text=f"refs/heads/main {head} refs/heads/main {self.base}\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

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

    def test_multi_commit_push_rejects_without_remote_head_audit(self) -> None:
        (self.repo / "docs" / "notes.md").write_text("notes updated\n", encoding="utf-8")
        run(["git", "add", "docs/notes.md"], self.repo)
        run(["git", "commit", "-m", "docs only"], self.repo)
        (self.repo / "utils" / "sample.py").write_text("print('changed again')\n", encoding="utf-8")
        run(["git", "add", "utils/sample.py"], self.repo)
        run(["git", "commit", "-m", "touch utils"], self.repo)
        head = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()

        result = run(
            ["python3", str(GUARD), "--repo", str(self.repo)],
            self.repo,
            input_text=f"refs/heads/main {head} refs/heads/main {self.base}\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"audit entry for parent hash {self.base}", result.stderr)

    def test_multi_commit_push_passes_with_remote_head_audit(self) -> None:
        (self.repo / "docs" / "notes.md").write_text("notes updated\n", encoding="utf-8")
        run(["git", "add", "docs/notes.md"], self.repo)
        run(["git", "commit", "-m", "docs only"], self.repo)
        (self.repo / "utils" / "sample.py").write_text("print('changed again')\n", encoding="utf-8")
        run(["git", "add", "utils/sample.py"], self.repo)
        run(["git", "commit", "-m", "touch utils"], self.repo)
        head = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()
        self.write_audit_log(
            f"- 2026-07-03 | audit {self.base} | canonical audit record for the push range parent."
        )

        result = run(
            ["python3", str(GUARD), "--repo", str(self.repo)],
            self.repo,
            input_text=f"refs/heads/main {head} refs/heads/main {self.base}\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_new_branch_push_uses_first_monitored_parent(self) -> None:
        with tempfile.TemporaryDirectory() as other_tmp:
            repo = Path(other_tmp)
            run(["git", "init"], repo)
            run(["git", "config", "user.name", "Test User"], repo)
            run(["git", "config", "user.email", "test@example.com"], repo)
            (repo / "docs").mkdir()
            (repo / "utils").mkdir()
            (repo / "docs" / "audit-log.md").write_text("# Audit Log\n\n", encoding="utf-8")
            (repo / "docs" / "notes.md").write_text("notes\n", encoding="utf-8")
            run(["git", "add", "."], repo)
            run(["git", "commit", "-m", "docs base"], repo)
            docs_commit = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
            (repo / "utils" / "sample.py").write_text("print('changed again')\n", encoding="utf-8")
            run(["git", "add", "utils/sample.py"], repo)
            run(["git", "commit", "-m", "touch utils"], repo)
            head = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
            (repo / "docs" / "audit-log.md").write_text(
                "# Audit Log\n\n"
                f"- 2026-07-03 | audit {docs_commit} | canonical audit record for the first monitored commit's parent on a new branch.\n",
                encoding="utf-8",
            )

            result = run(
                ["python3", str(GUARD), "--repo", str(repo)],
                repo,
                input_text=f"refs/heads/main {head} refs/heads/main {'0' * 40}\n",
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
