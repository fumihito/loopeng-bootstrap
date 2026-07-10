from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ._paths import agent_root
from .audit.report import run_audit_report
from .journal import append_event
from .okf.apply import apply_report
from .okf.index import reindex_bundle
from .okf.schema import validate_bundle
from .schedule import build_next_turn_prompt


def _path(value: str) -> Path:
    return Path(value).expanduser()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="loopeng")
    sub = parser.add_subparsers(dest="command", required=True)

    okf = sub.add_parser("okf")
    okf_sub = okf.add_subparsers(dest="okf_command", required=True)

    validate = okf_sub.add_parser("validate")
    validate.add_argument("bundle", type=_path)

    reindex = okf_sub.add_parser("reindex")
    reindex.add_argument("bundle", type=_path)

    log = okf_sub.add_parser("log")
    log.add_argument("bundle", type=_path)
    log.add_argument("--message", default="okf log entry")

    apply_cmd = okf_sub.add_parser("apply")
    apply_cmd.add_argument("report", type=_path)
    apply_cmd.add_argument("--bundle", type=_path, default=Path("llmwiki"))
    apply_cmd.add_argument("--backup-dir", type=_path, default=Path(agent_root("runtime", "okf-backups")))

    journal = sub.add_parser("journal")
    journal_sub = journal.add_subparsers(dest="journal_command", required=True)
    journal_add = journal_sub.add_parser("add")
    journal_add.add_argument("--run", required=True)
    journal_add.add_argument("--event", required=True)
    journal_add.add_argument("--repo", type=_path, default=Path("."))

    schedule = sub.add_parser("schedule")
    schedule_sub = schedule.add_subparsers(dest="schedule_command", required=True)
    schedule_next = schedule_sub.add_parser("next")
    schedule_next.add_argument("--repo", type=_path, default=Path("."))

    audit = sub.add_parser("audit")
    audit_sub = audit.add_subparsers(dest="audit_command", required=True)
    audit_run = audit_sub.add_parser("run")
    audit_run.add_argument("--run", required=True)
    audit_run.add_argument("--repo", type=_path, default=Path("."))

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "okf" and args.okf_command == "validate":
        result = validate_bundle(args.bundle)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1

    if args.command == "okf" and args.okf_command == "reindex":
        reindex_bundle(args.bundle)
        return 0

    if args.command == "okf" and args.okf_command == "log":
        reindex_bundle(args.bundle)
        log_path = args.bundle / "log.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"- {args.message}\n")
        return 0

    if args.command == "okf" and args.okf_command == "apply":
        result = apply_report(args.bundle, args.report, args.backup_dir)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1

    if args.command == "journal" and args.journal_command == "add":
        event = json.loads(args.event)
        path = append_event(args.repo, args.run, event)
        print(str(path))
        return 0

    if args.command == "schedule" and args.schedule_command == "next":
        sys.stdout.write(build_next_turn_prompt(args.repo))
        return 0

    if args.command == "audit" and args.audit_command == "run":
        report_path = run_audit_report(args.repo, args.run)
        print(str(report_path))
        return 0

    raise SystemExit("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())

