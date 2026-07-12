from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
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

    init = okf_sub.add_parser("init")
    init.add_argument("bundle", type=_path)

    reindex = okf_sub.add_parser("reindex")
    reindex.add_argument("bundle", type=_path)

    log = okf_sub.add_parser("log")
    log.add_argument("bundle", type=_path)
    log.add_argument("--message", default="okf log entry")

    apply_cmd = okf_sub.add_parser("apply")
    apply_cmd.add_argument("report", type=_path)
    apply_cmd.add_argument("--bundle", type=_path, default=Path("llmwiki"))
    apply_cmd.add_argument("--backup-dir", type=_path, default=Path(agent_root("runtime", "okf-backups")))
    apply_cmd.add_argument("--run")

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

    review = sub.add_parser("review")
    review.add_argument("--runs", type=int, default=5)
    review.add_argument("--repo", type=_path, default=Path("."))
    review.add_argument("--section", choices=("results", "concerns", "premises"))
    review.add_argument("--run")
    review.add_argument("--triage", action="store_true")
    review.add_argument("--next", dest="next_item", action="store_true")
    review.add_argument("--full", action="store_true")
    review.add_argument("--go")
    review.add_argument("--decision")
    review.add_argument("--choice", choices=("go", "alt", "hold"))
    review.add_argument("--format", choices=("text", "json"), default="text")

    status = sub.add_parser("status")
    status.add_argument("--repo", type=_path, default=Path("."))

    hook = sub.add_parser("hook")
    hook.add_argument("platform", choices=("claude-code", "codex"))

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "okf" and args.okf_command == "validate":
        result = validate_bundle(args.bundle)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1

    if args.command == "okf" and args.okf_command == "init":
        bundle = args.bundle
        bundle.mkdir(parents=True, exist_ok=True)
        for rel in ("concepts", "decisions", "constraints", "failure-patterns", "evaluation-rules", "recovery-patterns", "runbooks", "references"):
            (bundle / rel).mkdir(parents=True, exist_ok=True)
        index = bundle / "index.md"
        if not index.exists():
            index.write_text(
                "---\n"
                "okf_version: \"0.1\"\n"
                "title: \"Project LLMWiki\"\n"
                "description: \"Curated, version-controlled knowledge for coding agents.\"\n"
                "---\n\n"
                "# LLMWiki\n\n"
                "This bundle contains curated operational knowledge. Use the generated directory sections below for progressive disclosure.\n",
                encoding="utf-8",
            )
        log = bundle / "log.md"
        if not log.exists():
            log.write_text(
                "# Directory Update Log\n\n"
                f"## {datetime.now(timezone.utc).date().isoformat()}\n"
                "* **Initialization**: Created the OKF LLMWiki bundle.\n",
                encoding="utf-8",
            )
        reindex_bundle(bundle)
        return 0

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
        if args.run:
            append_event(Path(args.bundle).resolve().parent, args.run, {
                "kind": "okf-apply", "report": str(args.report), "ok": bool(result.get("ok")),
                "touched": result.get("touched", []),
            })
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

    if args.command == "review":
        from .review import execute_go, record_decision, render_review, render_triage, record_review
        if args.runs < 0:
            raise SystemExit("--runs must be non-negative")
        if args.go:
            print(execute_go(args.repo.resolve(), args.go, args.run), end="")
            return 0
        if args.decision:
            if not args.choice:
                raise SystemExit("--decision requires --choice")
            print(record_decision(args.repo.resolve(), args.decision, args.choice, args.run), end="")
            return 0
        if args.triage or args.next_item:
            print(render_triage(args.repo.resolve(), args.runs, next_item=args.next_item, as_json=args.format == "json"), end="")
            return 0
        print(render_review(args.repo.resolve(), args.runs, args.section), end="")
        if args.run:
            record_review(args.repo.resolve(), args.run, [args.section] if args.section else ["results", "concerns", "premises"])
        return 0

    if args.command == "status":
        from .status import render_status
        print(render_status(args.repo))
        return 0

    if args.command == "hook":
        raw = sys.stdin.read()
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if args.platform == "codex":
            from .hooks.codex import normalize, render
        else:
            from .hooks.claude_code import normalize, render
        event = normalize(payload)
        result = __import__("loopeng.hooks.handler", fromlist=["handle"]).handle(event)
        sys.stdout.write(json.dumps(render(result, event), ensure_ascii=False))
        return 0

    raise SystemExit("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
