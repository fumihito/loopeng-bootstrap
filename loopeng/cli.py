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
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        prog="loopeng",
        description="監査可能なエージェント運用ループを管理する CLI。",
        epilog=(
            "例:\n"
            "  loopeng status\n"
            "  loopeng okf validate llmwiki\n"
            "  loopeng review --triage"
        ),
        formatter_class=formatter,
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    okf = sub.add_parser(
        "okf", help="OKF LLMWiki の初期化・検証・更新・索引操作",
        description="OKF 形式の LLMWiki バンドルを管理します。",
        formatter_class=formatter,
    )
    okf_sub = okf.add_subparsers(dest="okf_command", required=True, metavar="COMMAND")

    validate = okf_sub.add_parser(
        "validate", help="LLMWiki の構造と文書を検証",
        description="LLMWiki バンドルを読み取り専用で検証し、結果を JSON で出力します。",
        formatter_class=formatter,
    )
    validate.add_argument("bundle", type=_path, help="検証する LLMWiki ディレクトリ")

    init = okf_sub.add_parser(
        "init", help="空の LLMWiki バンドルを作成",
        description="LLMWiki の標準ディレクトリ、index.md、log.md を作成します。",
        formatter_class=formatter,
    )
    init.add_argument("bundle", type=_path, help="作成する LLMWiki ディレクトリ")

    reindex = okf_sub.add_parser(
        "reindex", help="LLMWiki の索引を再生成",
        description="バンドル内の文書を走査し、index.md のディレクトリ索引を再生成します。",
        formatter_class=formatter,
    )
    reindex.add_argument("bundle", type=_path, help="索引を再生成する LLMWiki ディレクトリ")

    log = okf_sub.add_parser(
        "log", help="LLMWiki の更新ログに追記",
        description="LLMWiki の索引を更新し、log.md に一行追記します。",
        formatter_class=formatter,
    )
    log.add_argument("bundle", type=_path, help="更新する LLMWiki ディレクトリ")
    log.add_argument("--message", default="okf log entry", help="log.md に追加するメッセージ")

    apply_cmd = okf_sub.add_parser(
        "apply", help="検証済みレポートを LLMWiki に適用",
        description="トランザクションレポートを検証し、OKF LLMWiki に安全に適用します。",
        formatter_class=formatter,
    )
    apply_cmd.add_argument("report", type=_path, help="適用する JSON レポート")
    apply_cmd.add_argument("--bundle", type=_path, default=Path("llmwiki"), help="更新対象の LLMWiki (既定: llmwiki)")
    apply_cmd.add_argument("--backup-dir", type=_path, default=Path(agent_root("runtime", "okf-backups")), help="バックアップ先")
    apply_cmd.add_argument("--run", help="適用イベントを追記する run ID")

    journal = sub.add_parser(
        "journal", help="ランのイベントを journal に追記",
        description="実行中の run-start、intent、mutation、run-end などのイベントを記録します。",
        formatter_class=formatter,
    )
    journal_sub = journal.add_subparsers(dest="journal_command", required=True, metavar="COMMAND")
    journal_add = journal_sub.add_parser(
        "add", help="一つのイベントを追記",
        description="JSON イベントをサニタイズして run の journal に追記します。",
        formatter_class=formatter,
    )
    journal_add.add_argument("--run", required=True, help="イベントを属させる run ID")
    journal_add.add_argument("--event", required=True, help="追記する JSON イベント")
    journal_add.add_argument("--repo", type=_path, default=Path("."), help="対象リポジトリ (既定: .)")

    schedule = sub.add_parser(
        "schedule", help="次ターンの入力を生成",
        description="前回の handoff と Run Report から次ターン用のプロンプトを生成します。",
        formatter_class=formatter,
    )
    schedule_sub = schedule.add_subparsers(dest="schedule_command", required=True, metavar="COMMAND")
    schedule_next = schedule_sub.add_parser(
        "next", help="次ターンの handoff を表示",
        description="対象リポジトリの handoff を読み、次ターンの前文を標準出力へ出します。",
        formatter_class=formatter,
    )
    schedule_next.add_argument("--repo", type=_path, default=Path("."), help="対象リポジトリ (既定: .)")

    audit = sub.add_parser(
        "audit", help="Run Report と handoff を生成",
        description="journal とリポジトリ状態を監査し、Run Report と handoff を書き出します。",
        formatter_class=formatter,
    )
    audit_sub = audit.add_subparsers(dest="audit_command", required=True, metavar="COMMAND")
    audit_run = audit_sub.add_parser(
        "run", help="指定 run の監査を実行",
        description="指定した run の監査結果を .agent-loop/state/reports に保存します。",
        formatter_class=formatter,
    )
    audit_run.add_argument("--run", required=True, help="監査対象の run ID")
    audit_run.add_argument("--repo", type=_path, default=Path("."), help="対象リポジトリ (既定: .)")

    review = sub.add_parser(
        "review", help="過去の run 結果・懸念・前提をレビュー",
        description="Run Report の結果を一覧・トリアージし、判断や remediation を記録します。",
        formatter_class=formatter,
    )
    review.add_argument("--runs", type=int, default=5, help="表示対象にする直近 run 数 (既定: 5)")
    review.add_argument("--repo", type=_path, default=Path("."), help="対象リポジトリ (既定: .)")
    review.add_argument("--section", choices=("results", "concerns", "premises"), help="表示するセクションだけに絞る")
    review.add_argument("--run", help="レビュー記録を関連付ける run ID")
    review.add_argument("--triage", action="store_true", help="未確認項目をトリアージ表示")
    review.add_argument("--next", dest="next_item", action="store_true", help="次のトリアージ項目だけを表示")
    review.add_argument("--full", action="store_true", help="完全なレビュー表示を要求")
    review.add_argument("--go", help="指定したカタログ項目の remediation を実行")
    review.add_argument("--decision", help="判断 ID を記録")
    review.add_argument("--choice", choices=("go", "alt", "hold"), help="判断: go / alt / hold")
    review.add_argument("--format", choices=("text", "json"), default="text", help="出力形式 (既定: text)")

    status = sub.add_parser(
        "status", help="直近の Run Report と backlog を要約",
        description="対象リポジトリの最新状態、アラート、learning backlog を短く表示します。",
        formatter_class=formatter,
    )
    status.add_argument("--repo", type=_path, default=Path("."), help="対象リポジトリ (既定: .)")

    hook = sub.add_parser(
        "hook", help="エージェント hook のイベントを処理",
        description="標準入力の JSON hook イベントを正規化し、対応する hook 応答を JSON で出力します。",
        formatter_class=formatter,
    )
    hook.add_argument("platform", choices=("claude-code", "codex"), help="イベントを送信したプラットフォーム")

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
