from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("audit_guard_under_test", ROOT / "utils/audit_guard.py")
assert SPEC is not None and SPEC.loader is not None
audit_guard = importlib.util.module_from_spec(SPEC)
sys.modules["audit_guard_under_test"] = audit_guard
SPEC.loader.exec_module(audit_guard)


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)
    return completed.stdout.strip()


class AuditGuardRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.bare = self.root / "origin.git"
        self.repo = self.root / "repo"
        subprocess.run(["git", "init", "--bare", "-q", str(self.bare)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "Audit Test")
        (self.repo / "docs").mkdir()
        (self.repo / "docs/audit-log.md").write_text("# Audit log\n", encoding="utf-8")
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "initial")
        git(self.repo, "remote", "add", "origin", str(self.bare))
        git(self.repo, "push", "-q", "-u", "origin", "main")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def add_work_commit(self) -> None:
        (self.repo / "utils").mkdir(exist_ok=True)
        path = self.repo / "utils/change.txt"
        path.write_text(path.read_text(encoding="utf-8") + "changed\n" if path.exists() else "changed\n", encoding="utf-8")
        git(self.repo, "add", "utils/change.txt")
        git(self.repo, "commit", "-m", "work")

    def run_record(self, *, branch: str = "main", no_amend: bool = False) -> tuple[int, str, str]:
        with patch.object(audit_guard, "run_record_checks", return_value=audit_guard.CheckResult("fixture checks ok")):
            from contextlib import redirect_stderr, redirect_stdout
            from io import StringIO

            stdout, stderr = StringIO(), StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = audit_guard.record(self.repo, branch, None, no_amend=no_amend)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_amend_keeps_commit_count_and_uses_origin_hash(self) -> None:
        self.add_work_commit()
        before_count = len(git(self.repo, "rev-list", "--all").splitlines())
        origin_sha = git(self.repo, "rev-parse", "origin/main")
        code, stdout, stderr = self.run_record()
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("mode: amend", stdout)
        self.assertEqual(len(git(self.repo, "rev-list", "--all").splitlines()), before_count)
        self.assertIn(f"audit {origin_sha}", (self.repo / "docs/audit-log.md").read_text(encoding="utf-8"))
        self.assertNotEqual(git(self.repo, "rev-parse", "HEAD"), origin_sha)
        update = audit_guard.RefUpdate("refs/heads/main", git(self.repo, "rev-parse", "HEAD"), "refs/heads/main", origin_sha)
        self.assertEqual(audit_guard.evaluate_update(self.repo, update), (True, ""))

    def test_pushed_head_falls_back_to_separate_commit(self) -> None:
        self.add_work_commit()
        git(self.repo, "push", "-q", "origin", "main")
        pushed_head = git(self.repo, "rev-parse", "HEAD")
        code, stdout, stderr = self.run_record()
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("mode: separate (HEAD is already pushed)", stdout)
        self.assertNotEqual(git(self.repo, "rev-parse", "HEAD"), pushed_head)
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s"), "audit: record release gate")

    def test_detached_and_branch_mismatch_fall_back(self) -> None:
        self.add_work_commit()
        git(self.repo, "checkout", "-q", "--detach", "HEAD")
        code, stdout, stderr = self.run_record()
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("mode: separate (detached HEAD)", stdout)

        self.add_work_commit()
        git(self.repo, "checkout", "-q", "-b", "feature")
        code, stdout, stderr = self.run_record(branch="main")
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("mode: separate (branch mismatch", stdout)

    def test_dirty_worktree_is_rejected(self) -> None:
        (self.repo / "utils").mkdir(exist_ok=True)
        (self.repo / "utils/dirty.txt").write_text("dirty\n", encoding="utf-8")
        code, stdout, stderr = self.run_record()
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("requires a clean worktree", stderr)

    def test_self_verification_failure_is_nonzero(self) -> None:
        self.add_work_commit()

        def corrupt_append(root: Path, line: str) -> None:
            (root / "docs/audit-log.md").write_text("# corrupted\n", encoding="utf-8")

        with patch.object(audit_guard, "append_audit_line", side_effect=corrupt_append):
            code, stdout, stderr = self.run_record()
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("self-verification failed", stderr)

    def test_no_amend_is_explicit_separate_mode(self) -> None:
        self.add_work_commit()
        code, stdout, stderr = self.run_record(no_amend=True)
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("mode: separate (forced by --no-amend)", stdout)

    def test_merge_head_falls_back_to_separate_commit(self) -> None:
        self.add_work_commit()
        git(self.repo, "checkout", "-q", "-b", "side")
        (self.repo / "side.txt").write_text("side\n", encoding="utf-8")
        git(self.repo, "add", "side.txt")
        git(self.repo, "commit", "-m", "side")
        git(self.repo, "checkout", "-q", "main")
        (self.repo / "main.txt").write_text("main\n", encoding="utf-8")
        git(self.repo, "add", "main.txt")
        git(self.repo, "commit", "-m", "main")
        git(self.repo, "merge", "--no-ff", "-m", "merge", "side")
        code, stdout, stderr = self.run_record()
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("mode: separate (HEAD is a merge commit)", stdout)


if __name__ == "__main__":
    unittest.main()
