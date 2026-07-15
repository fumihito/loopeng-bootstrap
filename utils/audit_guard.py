#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import shutil
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


MONITORED_PREFIXES = (
    ".agent-loop/",
    "tests/",
    "utils/",
    "docs/loop-structure",
)
MONITORED_FILES = {"install.py"}
DOCS_PREFIX = "docs/"
AUDIT_LINE_PATTERN = r"(?m)^- \d{{4}}-\d{{2}}-\d{{2}} \| audit ({hash}) \|"
RECORD_FIX_TEMPLATE = (
    "To fix:\n"
    "  1) python3 utils/audit_guard.py record --branch {branch}\n"
    "     (audit line is committed automatically; amend into HEAD when safe)\n"
    "  2) git push"
)


@dataclass(frozen=True)
class RefUpdate:
    local_ref: str
    local_sha: str
    remote_ref: str
    remote_sha: str


def run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "git command failed").strip())
    return completed.stdout.strip()


def run_command(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_updates(stdin_text: str) -> list[RefUpdate]:
    updates: list[RefUpdate] = []
    for raw in stdin_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 4:
            continue
        updates.append(RefUpdate(*parts))
    return updates


def is_zero_sha(value: str) -> bool:
    return bool(value) and set(value) == {"0"}


def status_porcelain(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "git status failed").strip())
    return [line for line in completed.stdout.splitlines() if line.strip()]


def audit_log_only_dirty(root: Path, dirty: list[str]) -> bool:
    if not dirty:
        return True
    for line in dirty:
        if len(line) < 3:
            return False
        path = line[3:]
        if path != "docs/audit-log.md":
            return False
    return True


def changed_paths(root: Path, commit: str) -> list[str]:
    output = run_git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit)
    return [line.strip() for line in output.splitlines() if line.strip()]


def range_changed_paths(root: Path, remote_sha: str, local_sha: str) -> list[str]:
    if is_zero_sha(remote_sha):
        commits = commit_range(root, remote_sha, local_sha)
        paths: list[str] = []
        seen: set[str] = set()
        for commit in commits:
            for path in changed_paths(root, commit):
                if path not in seen:
                    seen.add(path)
                    paths.append(path)
        return paths
    output = run_git(root, "diff", "--name-only", f"{remote_sha}..{local_sha}")
    return [line.strip() for line in output.splitlines() if line.strip()]


def commit_range(root: Path, remote_sha: str, local_sha: str) -> list[str]:
    if is_zero_sha(local_sha):
        return []
    if is_zero_sha(remote_sha):
        output = run_git(root, "rev-list", "--reverse", local_sha)
    else:
        output = run_git(root, "rev-list", "--reverse", f"{remote_sha}..{local_sha}")
    return [line.strip() for line in output.splitlines() if line.strip()]


def commit_parent(root: Path, commit: str) -> str | None:
    output = run_git(root, "rev-list", "--parents", "-n", "1", commit)
    parts = output.split()
    if len(parts) < 2:
        return None
    return parts[1]


def is_docs_only(paths: list[str]) -> bool:
    return bool(paths) and all(path.startswith(DOCS_PREFIX) for path in paths)


def is_monitored_path(path: str) -> bool:
    return path in MONITORED_FILES or any(path.startswith(prefix) for prefix in MONITORED_PREFIXES)


def should_guard_commit(paths: list[str]) -> bool:
    if not paths:
        return False
    if is_docs_only(paths):
        return any(path.startswith("docs/loop-structure") for path in paths)
    return any(is_monitored_path(path) for path in paths)


def audit_log_text_at_commit(root: Path, commit: str) -> str | None:
    try:
        return run_git(root, "show", f"{commit}:docs/audit-log.md")
    except RuntimeError:
        return None


def audit_log_has_parent(root: Path, commit: str, parent_hash: str) -> bool:
    audit_log = audit_log_text_at_commit(root, commit)
    if audit_log is None:
        return False
    pattern = AUDIT_LINE_PATTERN.format(hash=re.escape(parent_hash))
    return bool(re.search(pattern, audit_log))


def branch_name(ref: str) -> str:
    prefix = "refs/heads/"
    if ref.startswith(prefix):
        return ref.removeprefix(prefix)
    return ref


def refusal_message(update: RefUpdate, parent_hash: str, touched_paths: list[str], *, absent: bool = False) -> str:
    touched = ", ".join(touched_paths[:6]) if touched_paths else "<none>"
    branch = branch_name(update.local_ref)
    audit_clause = (
        f"docs/audit-log.md in commit {update.local_sha} is absent or does not contain an audit entry for parent hash {parent_hash}"
        if absent
        else f"docs/audit-log.md in commit {update.local_sha} does not contain an audit entry for parent hash {parent_hash}"
    )
    return (
        "pre-push audit guard blocked the push: "
        f"the pushed range touches audited paths ({touched}) "
        f"but {audit_clause}.\n"
        + RECORD_FIX_TEMPLATE.format(branch=branch)
    )


def evaluate_update(root: Path, update: RefUpdate) -> tuple[bool, str]:
    commits = commit_range(root, update.remote_sha, update.local_sha)
    if not commits:
        return True, ""
    touched_paths = range_changed_paths(root, update.remote_sha, update.local_sha)
    if not should_guard_commit(touched_paths):
        return True, ""
    if is_zero_sha(update.remote_sha):
        first_commit = next((commit for commit in commits if should_guard_commit(changed_paths(root, commit))), None)
        if first_commit is None:
            return True, ""
        parent_hash = commit_parent(root, first_commit)
        if parent_hash is None:
            return False, (
                f"pre-push audit guard cannot evaluate root commit {first_commit[:12]}: no parent hash is available.\n"
                + RECORD_FIX_TEMPLATE.format(branch=branch_name(update.local_ref))
            )
    else:
        parent_hash = update.remote_sha
    if audit_log_has_parent(root, update.local_sha, parent_hash):
        return True, ""
    absent = audit_log_text_at_commit(root, update.local_sha) is None
    return False, refusal_message(update, parent_hash, touched_paths, absent=absent)


@dataclass(frozen=True)
class RecordRun:
    summary: str
    test_runner: str
    tests_passed: int
    tests_skipped: int


def run_test_suite(root: Path) -> RecordRun:
    pytest = shutil.which("pytest")
    if pytest:
        completed = run_command(root, pytest, "tests", "-q")
        if completed.returncode != 0:
            raise RuntimeError(
                "pytest tests failed:\n"
                f"{(completed.stdout or '').strip()}\n{(completed.stderr or '').strip()}".strip()
            )
        passed = sum(int(value) for value in re.findall(r"(\d+) passed", completed.stdout))
        skipped = sum(int(value) for value in re.findall(r"(\d+) skipped", completed.stdout))
        return RecordRun(
            summary=f"tests {passed} passed {skipped} skipped; runner=pytest",
            test_runner="pytest",
            tests_passed=passed,
            tests_skipped=skipped,
        )

    completed = run_command(root, sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q")
    if completed.returncode != 0:
        raise RuntimeError(
            "unittest discover failed:\n"
            f"{(completed.stdout or '').strip()}\n{(completed.stderr or '').strip()}".strip()
        )
    combined_output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    total_match = re.search(r"Ran (\d+) tests?", combined_output)
    if total_match is None:
        raise RuntimeError("unittest discover succeeded but did not report a test count")
    skipped_match = re.search(r"skipped=(\d+)", combined_output)
    total = int(total_match.group(1))
    skipped = int(skipped_match.group(1)) if skipped_match else 0
    passed = total - skipped
    return RecordRun(
        summary=f"tests {passed} passed {skipped} skipped; runner=unittest",
        test_runner="unittest",
        tests_passed=passed,
        tests_skipped=skipped,
    )


@dataclass(frozen=True)
class CheckResult:
    summary: str
    error: str | None = None


def run_named_check(root: Path, label: str, *args: str) -> CheckResult:
    completed = run_command(root, *args)
    if completed.returncode != 0:
        output = (completed.stdout or "") + (completed.stderr or "")
        return CheckResult(
            summary="",
            error=f"ERROR: {label} failed:\n{output.strip()}",
        )
    return CheckResult(summary=f"{label} ok")


def install_manifest_path(root: Path) -> Path:
    return root / ".agent-loop/runtime/install-manifest.json"


def manifest_integrity_check(root: Path) -> CheckResult:
    path = install_manifest_path(root)
    if not path.is_file():
        return CheckResult(summary="install integrity skipped; install manifest absent")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return CheckResult(summary="", error=f"ERROR: install manifest is unreadable: {exc}")
    entries = manifest.get("entries") if isinstance(manifest, dict) else None
    if not isinstance(entries, list):
        return CheckResult(summary="", error="ERROR: install manifest entries are missing or invalid")

    for item in entries:
        if not isinstance(item, dict):
            return CheckResult(summary="", error="ERROR: install manifest contains a non-object entry")
        rel = str(item.get("relative_path") or "").strip()
        classification = str(item.get("classification") or "")
        recorded_sha = str(item.get("sha256") or "")
        recorded_source_sha = str(item.get("source_sha256") or "")
        source_rel = str(item.get("source_rel") or "").strip()
        if not rel or not recorded_sha:
            return CheckResult(summary="", error=f"ERROR: install manifest entry is incomplete: {rel or '<unknown>'}")
        if classification != "generated":
            continue
        target = root / rel
        if not target.is_file():
            return CheckResult(summary="", error=f"ERROR: installed file is missing: {rel}")
        current_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        if current_sha != recorded_sha:
            return CheckResult(
                summary="",
                error=(
                    "ERROR: installed file changed since install manifest was written: "
                    f"{rel}\n"
                    "To fix:\n"
                    "  1) python3 install.py --self --update\n"
                    "  2) git add .agent-loop/runtime/install-manifest.json\n"
                    "  3) rerun record"
                ),
            )
        if source_rel and recorded_source_sha:
            source = root / source_rel
            if not source.is_file():
                return CheckResult(summary="", error=f"ERROR: source file referenced by install manifest is missing: {source_rel}")
            expected_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            if expected_sha != recorded_source_sha:
                return CheckResult(
                    summary="",
                    error=(
                        "ERROR: source changed after install manifest was written: "
                        f"{source_rel}\n"
                        "To fix:\n"
                        "  1) python3 install.py --self --update\n"
                        "  2) git add .agent-loop/runtime/install-manifest.json\n"
                        "  3) rerun record"
                    ),
                )

    return CheckResult(summary="install integrity ok")


def skill_tree_integrity_check(root: Path) -> CheckResult:
    source_root = root / "adapters/shared/skills"
    installed_root = root / "skills"
    if not source_root.is_dir():
        return CheckResult(summary="skill tree integrity skipped; adapters/shared/skills absent")
    if not installed_root.is_dir():
        return CheckResult(
            summary="",
            error=(
                "ERROR: installed skill tree is missing or invalid: skills\n"
                "To fix:\n"
                "  1) python3 install.py --self --update\n"
                "  2) rerun record"
            ),
        )

    source_files = {
        path.relative_to(source_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    installed_files = {
        path.relative_to(installed_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in installed_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    missing = sorted(set(source_files) - set(installed_files))
    extra = sorted(set(installed_files) - set(source_files))
    mismatched = sorted(
        rel for rel in source_files.keys() & installed_files.keys()
        if source_files[rel] != installed_files[rel]
    )
    if missing or extra or mismatched:
        details: list[str] = []
        if missing:
            details.append(f"missing: {', '.join(missing[:8])}")
        if extra:
            details.append(f"extra: {', '.join(extra[:8])}")
        if mismatched:
            details.append(f"mismatched: {', '.join(mismatched[:8])}")
        return CheckResult(
            summary="",
            error=(
                "ERROR: installed skill tree diverged from adapters/shared/skills: "
                + "; ".join(details)
                + "\nTo fix:\n"
                "  1) python3 install.py --self --update\n"
                "  2) rerun record"
            ),
        )

    return CheckResult(summary="skill tree integrity ok")


def run_record_checks(root: Path) -> CheckResult:
    parts: list[str] = []
    try:
        tests = run_test_suite(root)
    except RuntimeError as exc:
        return CheckResult(summary="", error=f"ERROR: {exc}")
    parts.append(tests.summary)
    integrity = manifest_integrity_check(root)
    if integrity.error:
        return integrity
    parts.append(integrity.summary)
    tree = skill_tree_integrity_check(root)
    if tree.error:
        return tree
    parts.append(tree.summary)
    for label, args in [
        ("doc parity lint", (sys.executable, str(root / "utils/doc_parity_lint.py"), "--root", str(root))),
        ("protocol lint", (sys.executable, str(root / "utils/completion_protocol_lint.py"), "--root", str(root))),
        ("skill structure lint", (sys.executable, str(root / "utils/skill_structure_lint.py"), "--root", str(root))),
        ("distribution lint", (sys.executable, str(root / "utils/distribution_lint.py"), "--root", str(root))),
        ("routing hints lint", (sys.executable, str(root / "utils/routing_hints_lint.py"), "--root", str(root))),
    ]:
        result = run_named_check(root, label, *args)
        if result.error:
            return result
        parts.append(result.summary)
    return CheckResult(summary="; ".join(parts))


def append_audit_line(root: Path, line: str) -> None:
    audit_log = root / "docs/audit-log.md"
    if not audit_log.is_file():
        raise RuntimeError(f"missing audit log: {audit_log}")
    body = audit_log.read_text(encoding="utf-8")
    if body and not body.endswith("\n"):
        body += "\n"
    body += line.rstrip() + "\n"
    audit_log.write_text(body, encoding="utf-8")


def _command_succeeds(root: Path, *args: str) -> bool:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def amend_fallback_reason(root: Path, branch: str, *, no_amend: bool) -> str | None:
    if no_amend:
        return "forced by --no-amend"
    if not _command_succeeds(root, "rev-parse", "--verify", "HEAD"):
        return "HEAD does not exist"
    if not _command_succeeds(root, "symbolic-ref", "--quiet", "--short", "HEAD"):
        return "detached HEAD"
    current_branch = run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if current_branch != branch_name(branch):
        return f"branch mismatch (current: {current_branch}, requested: {branch_name(branch)})"
    if _command_succeeds(root, "merge-base", "--is-ancestor", "HEAD", f"origin/{branch}"):
        return "HEAD is already pushed"
    if len(run_git(root, "rev-list", "--parents", "-n", "1", "HEAD").split()) > 2:
        return "HEAD is a merge commit"
    return None


def record(root: Path, branch: str, summary: str | None, *, no_amend: bool = False) -> int:
    try:
        parent_hash = run_git(root, "rev-parse", f"origin/{branch}")
    except RuntimeError as exc:
        print(f"ERROR: cannot resolve origin/{branch}: {exc}", file=sys.stderr)
        return 1

    dirty = status_porcelain(root)
    if dirty and not audit_log_only_dirty(root, dirty):
        print("ERROR: record requires a clean worktree before running checks:", file=sys.stderr)
        for line in dirty:
            print(line, file=sys.stderr)
        return 1

    checks = run_record_checks(root)
    if checks.error is not None:
        print(checks.error, file=sys.stderr)
        return 1

    post_checks_dirty = status_porcelain(root)
    if post_checks_dirty and not audit_log_only_dirty(root, post_checks_dirty):
        print("ERROR: record checks mutated the worktree; refusing to write docs/audit-log.md", file=sys.stderr)
        return 1

    final_summary = checks.summary
    if summary:
        final_summary = f"{final_summary}; {summary}"
    line = f"- {datetime.now().astimezone().strftime('%Y-%m-%d')} | audit {parent_hash} | {final_summary}"
    try:
        append_audit_line(root, line)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    fallback_reason = amend_fallback_reason(root, branch, no_amend=no_amend)
    mode = "amend"
    if fallback_reason is None:
        try:
            run_git(root, "add", "docs/audit-log.md")
            run_git(root, "commit", "--amend", "--no-edit")
        except RuntimeError as exc:
            print(f"ERROR: amend commit failed: {exc}", file=sys.stderr)
            return 1
    else:
        mode = f"separate ({fallback_reason})"
        try:
            run_git(root, "add", "docs/audit-log.md")
            run_git(root, "commit", "-m", "audit: record release gate")
        except RuntimeError as exc:
            print(f"ERROR: separate audit commit failed: {exc}", file=sys.stderr)
            return 1

    try:
        head = run_git(root, "rev-parse", "HEAD")
    except RuntimeError as exc:
        print(f"ERROR: cannot resolve committed HEAD: {exc}", file=sys.stderr)
        return 1
    audit_log = audit_log_text_at_commit(root, head)
    pattern = AUDIT_LINE_PATTERN.format(hash=re.escape(parent_hash))
    if audit_log is None or not re.search(pattern, audit_log):
        print(
            f"ERROR: self-verification failed: HEAD {head} does not contain the audit line for {parent_hash}",
            file=sys.stderr,
        )
        return 1

    print(line)
    print(f"HEAD: {head}")
    print(f"mode: {mode}")
    print("次の手順: `git push`")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic pre-push audit guard for release-tracked changes.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root. Defaults to the current directory.")
    subparsers = parser.add_subparsers(dest="command")
    record_parser = subparsers.add_parser("record", help="Run the release checklist and append an audit log entry.")
    record_parser.add_argument("--branch", default="main", help="Branch whose origin ref supplies the audit hash.")
    record_parser.add_argument("--summary", default=None, help="Optional free-form note appended to the audit summary.")
    amend_group = record_parser.add_mutually_exclusive_group()
    amend_group.add_argument("--amend", action="store_true", help="Amend the audit line into HEAD when safe (default).")
    amend_group.add_argument("--no-amend", action="store_true", help="Always create a separate audit commit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.repo.resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: repository root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2

    if args.command == "record":
        return record(root, args.branch, args.summary, no_amend=args.no_amend)

    updates = parse_updates(sys.stdin.read())
    if not updates:
        return 0

    for update in updates:
        try:
            ok, message = evaluate_update(root, update)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if not ok:
            print(message, file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
