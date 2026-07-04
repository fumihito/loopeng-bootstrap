from __future__ import annotations

import contextlib
import io
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "utils/audit_guard.py"
INSTALL = ROOT / "utils/install-dev-hooks.sh"


def run(cmd: list[str], cwd: Path, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, input=input_text, text=True, capture_output=True, check=False)


def load_guard_module():
    spec = importlib.util.spec_from_file_location("audit_guard_under_test", GUARD)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys_modules_key = spec.name
    import sys
    sys.modules[sys_modules_key] = module
    spec.loader.exec_module(module)
    return module


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
        run(["git", "update-ref", "refs/remotes/origin/main", self.base], self.repo)

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
        self.assertIn("To fix:", result.stderr)
        self.assertIn("python3 utils/audit_guard.py record --branch main", result.stderr)
        self.assertIn('git commit -m "audit: record release gate"', result.stderr)
        self.assertIn("git push", result.stderr)

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
        run(["git", "add", "docs/audit-log.md"], self.repo)
        run(["git", "commit", "-m", "audit log"], self.repo)
        head = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()

        result = run(
            ["python3", str(GUARD), "--repo", str(self.repo)],
            self.repo,
            input_text=f"refs/heads/main {head} refs/heads/main {self.base}\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_worktree_only_audit_line_does_not_satisfy_guard(self) -> None:
        (self.repo / "utils" / "sample.py").write_text("print('changed')\n", encoding="utf-8")
        run(["git", "add", "utils/sample.py"], self.repo)
        run(["git", "commit", "-m", "touch utils"], self.repo)
        head = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()
        self.write_audit_log(
            f"- 2026-07-03 | audit {self.base} | worktree-only audit record must not satisfy the guard."
        )

        result = run(
            ["python3", str(GUARD), "--repo", str(self.repo)],
            self.repo,
            input_text=f"refs/heads/main {head} refs/heads/main {self.base}\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"audit entry for parent hash {self.base}", result.stderr)

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
        self.write_audit_log(
            f"- 2026-07-03 | audit {self.base} | canonical audit record for the push range parent."
        )
        run(["git", "add", "docs/audit-log.md"], self.repo)
        run(["git", "commit", "-m", "audit log"], self.repo)
        head = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()

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
            (repo / "docs" / "audit-log.md").write_text(
                "# Audit Log\n\n"
                f"- 2026-07-03 | audit {docs_commit} | canonical audit record for the first monitored commit's parent on a new branch.\n",
                encoding="utf-8",
            )
            run(["git", "add", "docs/audit-log.md"], repo)
            run(["git", "commit", "-m", "audit log"], repo)
            head = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

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

    def test_record_writes_audit_entry_and_next_step(self) -> None:
        module = load_guard_module()
        with mock.patch.object(module, "run_record_checks", return_value=module.CheckResult(summary="tests 1 passed 0 skipped; runner=pytest; journal lint ok; routing lint ok; protocol lint ok; self-test ok")):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                result = module.record(self.repo, "main", "manual summary")
        self.assertEqual(result, 0)
        self.assertIn("次の手順: `git add docs/audit-log.md && git commit` してから push", stream.getvalue())
        audit_log = (self.repo / "docs" / "audit-log.md").read_text(encoding="utf-8")
        self.assertIn(f"- {datetime.now().astimezone().strftime('%Y-%m-%d')} | audit {self.base} | tests 1 passed 0 skipped; runner=pytest; journal lint ok; routing lint ok; protocol lint ok; self-test ok; manual summary", audit_log)

    def test_record_rejects_dirty_tree(self) -> None:
        module = load_guard_module()
        (self.repo / "docs" / "notes.md").write_text("dirty\n", encoding="utf-8")
        with mock.patch.object(module, "run_record_checks") as run_checks:
            with mock.patch("builtins.print") as fake_print:
                result = module.record(self.repo, "main", None)
        self.assertEqual(result, 1)
        run_checks.assert_not_called()
        self.assertTrue(any("clean worktree" in str(call.args[0]) for call in fake_print.call_args_list))

    def test_record_allows_only_audit_log_dirty_tree(self) -> None:
        module = load_guard_module()
        (self.repo / "docs" / "audit-log.md").write_text(
            "# Audit Log\n\n- 2026-07-03 | note deadbeef | pre-existing note.\n",
            encoding="utf-8",
        )
        with mock.patch.object(module, "run_record_checks", return_value=module.CheckResult(summary="tests 1 passed 0 skipped; runner=pytest")):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                result = module.record(self.repo, "main", None)
        self.assertEqual(result, 0)
        self.assertIn("次の手順: `git add docs/audit-log.md && git commit` してから push", stream.getvalue())

    def test_skill_tree_integrity_detects_drift(self) -> None:
        module = load_guard_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "adapters/shared/skills/frame-sample"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(
                """---
name: frame-sample
description: \"Test frame for integrity checking. Use when the example needs syncing. The point is to stay short.\"
user-invocable: true
---

## Purpose

Test frame.

## When to use

- sample

## Workflow

1. sample

## Output

- sample

## Exit

- sample

## Adjacent frames

- sample
""",
                encoding="utf-8",
            )
            installed = root / "skills/frame-sample"
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text(
                """---
name: frame-sample
description: \"Test frame for integrity checking. Use when the example needs syncing. The point is to stay short.\"
user-invocable: true
---

## Purpose

Changed frame.

## When to use

- sample

## Workflow

1. sample

## Output

- sample

## Exit

- sample

## Adjacent frames

- sample
""",
                encoding="utf-8",
            )

            result = module.skill_tree_integrity_check(root)
            self.assertIsNotNone(result.error)
            self.assertIn("install.py --self --update", result.error)

    def test_run_test_suite_falls_back_to_unittest(self) -> None:
        module = load_guard_module()
        fake_output = "Ran 8 tests in 0.1s\n\nOK (skipped=2)\n"
        completed = subprocess.CompletedProcess(args=["python3"], returncode=0, stdout=fake_output, stderr="")
        with mock.patch.object(module.shutil, "which", return_value=None):
            with mock.patch.object(module, "run_command", return_value=completed):
                result = module.run_test_suite(self.repo)
        self.assertEqual(result.test_runner, "unittest")
        self.assertEqual(result.tests_passed, 6)
        self.assertEqual(result.tests_skipped, 2)
        self.assertIn("runner=unittest", result.summary)


if __name__ == "__main__":
    unittest.main()
