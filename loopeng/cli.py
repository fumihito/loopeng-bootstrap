from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from ._paths import agent_root
from .audit.report import run_audit_report
from .journal import EVENT_OKF_APPLY, EVENT_MEMORY_DRAFT, EVENT_RETRIEVAL, append_event
from .okf.apply import apply_report
from .okf.index import reindex_bundle
from .okf.schema import validate_bundle
from .okf.query import query_bundle
from .okf.draft import make_draft
from .okf.promote import promote, establish
from .okf.curate import curate
from .okf.approval import approve, list_drafts, reject, show_draft, snooze
from .schedule import build_next_turn_prompt
from .memory_stats import STATS_WINDOWS, collect_stats, render_stats
from .run import record_human_outcome, verify_run
from .doctor import doctor
from .memory_efficacy import collect_efficacy, render_efficacy
from .inbox import render_inbox
from .run_stats import collect_run_stats, render_run_stats
from .audit.export import export_packet
from .review_intake import intake
from .review_request import build_request


def _path(value: str) -> Path:
    return Path(value).expanduser()


def build_parser() -> argparse.ArgumentParser:
    formatter = argparse.RawDescriptionHelpFormatter
    lang = os.environ.get("LANG", "")
    english = bool(lang) and not lang.lower().startswith("ja")

    def t(japanese: str, english_text: str) -> str:
        return english_text if english else japanese

    parser = argparse.ArgumentParser(
        prog="loopeng",
        description=t("監査可能なエージェント運用ループを管理する CLI。", "CLI for operating auditable agent loops."),
        epilog=(
            t(
                "例:\n  loopeng status\n  loopeng okf validate llmwiki\n  loopeng review --triage",
                "Examples:\n  loopeng status\n  loopeng okf validate llmwiki\n  loopeng review --triage",
            )
        ),
        formatter_class=formatter,
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    okf = sub.add_parser(
        "okf", help=t("OKF LLMWiki の初期化・検証・更新・索引操作", "Initialize, validate, update, and index OKF LLMWiki"),
        description=t("OKF 形式の LLMWiki バンドルを管理します。", "Manage OKF-format LLMWiki bundles."),
        formatter_class=formatter,
    )
    okf_sub = okf.add_subparsers(dest="okf_command", required=True, metavar="COMMAND")

    validate = okf_sub.add_parser(
        "validate", help=t("LLMWiki の構造と文書を検証", "Validate LLMWiki structure and documents"),
        description=t("LLMWiki バンドルを読み取り専用で検証し、結果を JSON で出力します。", "Validate an LLMWiki bundle read-only and print the result as JSON."),
        formatter_class=formatter,
    )
    validate.add_argument("bundle", type=_path, help=t("検証する LLMWiki ディレクトリ", "LLMWiki directory to validate"))

    init = okf_sub.add_parser(
        "init", help=t("空の LLMWiki バンドルを作成", "Create an empty LLMWiki bundle"),
        description=t("LLMWiki の標準ディレクトリ、index.md、log.md を作成します。", "Create the standard LLMWiki directories, index.md, and log.md."),
        formatter_class=formatter,
    )
    init.add_argument("bundle", type=_path, help=t("作成する LLMWiki ディレクトリ", "LLMWiki directory to create"))

    reindex = okf_sub.add_parser(
        "reindex", help=t("LLMWiki の索引を再生成", "Rebuild the LLMWiki index"),
        description=t("バンドル内の文書を走査し、index.md のディレクトリ索引を再生成します。", "Scan bundle documents and rebuild the directory index in index.md."),
        formatter_class=formatter,
    )
    reindex.add_argument("bundle", type=_path, help=t("索引を再生成する LLMWiki ディレクトリ", "LLMWiki directory to reindex"))

    log = okf_sub.add_parser(
        "log", help=t("LLMWiki の更新ログに追記", "Append to the LLMWiki update log"),
        description=t("LLMWiki の索引を更新し、log.md に一行追記します。", "Update the LLMWiki index and append one line to log.md."),
        formatter_class=formatter,
    )
    log.add_argument("bundle", type=_path, help=t("更新する LLMWiki ディレクトリ", "LLMWiki directory to update"))
    log.add_argument("--message", default="okf log entry", help=t("log.md に追加するメッセージ", "Message to append to log.md"))

    apply_cmd = okf_sub.add_parser(
        "apply", help=t("検証済みレポートを LLMWiki に適用", "Apply a validated report to LLMWiki"),
        description=t("トランザクションレポートを検証し、OKF LLMWiki に安全に適用します。", "Validate a transaction report and safely apply it to an OKF LLMWiki."),
        formatter_class=formatter,
    )
    apply_cmd.add_argument("report", type=_path, help=t("適用する JSON レポート", "JSON report to apply"))
    apply_cmd.add_argument("--bundle", type=_path, default=Path("llmwiki"), help=t("更新対象の LLMWiki (既定: llmwiki)", "LLMWiki to update (default: llmwiki)"))
    apply_cmd.add_argument("--backup-dir", type=_path, default=Path(agent_root("runtime", "okf-backups")), help=t("バックアップ先", "Backup directory"))
    apply_cmd.add_argument("--run", help=t("適用イベントを追記する run ID", "Run ID for recording the apply event"))

    query = okf_sub.add_parser("query", help=t("決定論的にメモリを検索", "Deterministically query memory"))
    query.add_argument("bundle", type=_path)
    query.add_argument("--type", dest="type_name")
    query.add_argument("--tag", action="append", default=[])
    query.add_argument("--grep")
    query.add_argument("--status", choices=("active", "deprecated", "all"), default="active")
    query.add_argument("--limit", type=int, default=10)
    query.add_argument("--run")
    query.add_argument("--tier", choices=("all", "provisional", "established"), default="all")
    query.add_argument("--space", choices=("current", "framework", "project", "all"), default="current")

    memory = sub.add_parser("memory", help=t("自律メモリの起案・適用", "Curate bounded autonomous memory"))
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    curate_cmd = memory_sub.add_parser("curate", help=t("learning を起案し安全な provisional のみ適用", "Promote learning and apply safe provisional entries"))
    curate_cmd.add_argument("--repo", type=_path, default=Path("."))
    curate_cmd.add_argument("--run")
    curate_cmd.add_argument("--top", type=int, default=3)
    drafts_cmd = memory_sub.add_parser("drafts", help=t("承認待ち draft を一覧・表示", "List or show pending memory drafts"))
    drafts_sub = drafts_cmd.add_subparsers(dest="drafts_command", required=True)
    drafts_list = drafts_sub.add_parser("list")
    drafts_list.add_argument("--repo", type=_path, default=Path("."))
    drafts_show = drafts_sub.add_parser("show")
    drafts_show.add_argument("id")
    drafts_show.add_argument("--repo", type=_path, default=Path("."))
    approve_cmd = memory_sub.add_parser("approve", help=t("明示承認した draft を適用", "Apply explicitly approved drafts"))
    approve_cmd.add_argument("ids", nargs="*")
    approve_cmd.add_argument("--all", action="store_true")
    approve_cmd.add_argument("--quote", required=True)
    approve_cmd.add_argument("--run")
    approve_cmd.add_argument("--repo", type=_path, default=Path("."))
    reject_cmd = memory_sub.add_parser("reject", help=t("draft を却下して保存", "Reject and retain a draft"))
    reject_cmd.add_argument("id")
    reject_cmd.add_argument("--reason", required=True)
    reject_cmd.add_argument("--run")
    reject_cmd.add_argument("--repo", type=_path, default=Path("."))
    snooze_cmd = memory_sub.add_parser("snooze", help=t("承認要請を一時停止", "Snooze approval requests"))
    snooze_cmd.add_argument("--days", type=int, default=3)
    snooze_cmd.add_argument("--run")
    snooze_cmd.add_argument("--repo", type=_path, default=Path("."))
    stats_cmd = memory_sub.add_parser("stats", help=t("メモリ更新とコミット活動を集計", "Summarize memory updates and commit activity"))
    stats_cmd.add_argument("--repo", type=_path, default=Path("."))
    stats_cmd.add_argument("--bundle", type=_path, default=Path("llmwiki"))
    stats_cmd.add_argument("--windows", default=",".join(STATS_WINDOWS))
    stats_cmd.add_argument("--format", choices=("text", "json"), default="text")
    stats_cmd.add_argument("--now")
    stats_cmd.add_argument("--space", choices=("current", "framework", "project", "all"), default="current")
    efficacy_cmd = memory_sub.add_parser("efficacy", help=t("学習の再発効力を集計", "Measure learning efficacy"), formatter_class=formatter)
    efficacy_cmd.add_argument("--repo", type=_path, default=Path("."))
    efficacy_cmd.add_argument("--windows", default="7d,28d")
    efficacy_cmd.add_argument("--now")
    efficacy_cmd.add_argument("--space", choices=("current", "framework", "project", "all"), default="current")

    learning = sub.add_parser("learning", help=t("learning 起案を管理", "Manage learning proposals"))
    learning_sub = learning.add_subparsers(dest="learning_command", required=True)
    promote_cmd = learning_sub.add_parser("promote", help=t("learning から draft を生成", "Generate drafts from learning"))
    promote_cmd.add_argument("--repo", type=_path, default=Path("."))
    promote_cmd.add_argument("--top", type=int, default=3)
    promote_cmd.add_argument("--ids", nargs="*")
    promote_cmd.add_argument("--type", dest="type_name", default="Concept")
    promote_cmd.add_argument("--run")
    promote_cmd.add_argument("--establish", nargs="*")

    draft_cmd = okf_sub.add_parser("draft", help=t("一般知識の draft を生成", "Generate a knowledge draft"))
    draft_cmd.add_argument("--type", dest="type_name", required=True)
    draft_cmd.add_argument("--concept-id", required=True)
    draft_cmd.add_argument("--title", required=True)
    draft_cmd.add_argument("--tags", default="")
    draft_cmd.add_argument("--body-file", type=_path)

    journal = sub.add_parser(
        "journal", help=t("ランのイベントを journal に追記", "Append run events to the journal"),
        description=t("実行中の run-start、intent、mutation、run-end などのイベントを記録します。", "Record run-start, intent, mutation, run-end, and other events."),
        formatter_class=formatter,
    )
    journal_sub = journal.add_subparsers(dest="journal_command", required=True, metavar="COMMAND")
    journal_add = journal_sub.add_parser(
        "add", help=t("一つのイベントを追記", "Append one event"),
        description=t("JSON イベントをサニタイズして run の journal に追記します。", "Sanitize a JSON event and append it to a run journal."),
        formatter_class=formatter,
    )
    journal_add.add_argument("--run", required=True, help=t("イベントを属させる run ID", "Run ID that owns the event"))
    journal_add.add_argument("--event", required=True, help=t("追記する JSON イベント", "JSON event to append"))
    journal_add.add_argument("--repo", type=_path, default=Path("."), help=t("対象リポジトリ (既定: .)", "Target repository (default: .)"))

    schedule = sub.add_parser(
        "schedule", help=t("次ターンの入力を生成", "Generate next-turn input"),
        description=t("前回の handoff と Run Report から次ターン用のプロンプトを生成します。", "Generate the next-turn prompt from the previous handoff and Run Report."),
        formatter_class=formatter,
    )
    schedule_sub = schedule.add_subparsers(dest="schedule_command", required=True, metavar="COMMAND")
    schedule_next = schedule_sub.add_parser(
        "next", help=t("次ターンの handoff を表示", "Show the next-turn handoff"),
        description=t("対象リポジトリの handoff を読み、次ターンの前文を標準出力へ出します。", "Read the repository handoff and print the next-turn preamble."),
        formatter_class=formatter,
    )
    schedule_next.add_argument("--repo", type=_path, default=Path("."), help=t("対象リポジトリ (既定: .)", "Target repository (default: .)"))

    audit = sub.add_parser(
        "audit", help=t("Run Report と handoff を生成", "Generate a Run Report and handoff"),
        description=t("journal とリポジトリ状態を監査し、Run Report と handoff を書き出します。", "Audit the journal and repository state, then write a Run Report and handoff."),
        formatter_class=formatter,
    )
    audit_sub = audit.add_subparsers(dest="audit_command", required=True, metavar="COMMAND")
    audit_run = audit_sub.add_parser(
        "run", help=t("指定 run の監査を実行", "Audit a specified run"),
        description=t("指定した run の監査結果を .agent-loop/state/reports に保存します。", "Save the audit result for a run under .agent-loop/state/reports."),
        formatter_class=formatter,
    )
    audit_run.add_argument("--run", required=True, help=t("監査対象の run ID", "Run ID to audit"))
    audit_run.add_argument("--repo", type=_path, default=Path("."), help=t("対象リポジトリ (既定: .)", "Target repository (default: .)"))
    audit_export = audit_sub.add_parser("export", help=t("レビューパケットを出力", "Export a review packet"), formatter_class=formatter)
    audit_export.add_argument("--run", required=True)
    audit_export.add_argument("--repo", type=_path, default=Path("."))

    review = sub.add_parser(
        "review", help=t("過去の run 結果・懸念・前提をレビュー", "Review past run results, concerns, and premises"),
        description=t("Run Report の結果を一覧・トリアージし、判断や remediation を記録します。", "List and triage Run Report results, then record decisions or remediation."),
        formatter_class=formatter,
    )
    review.add_argument("review_view", nargs="?", choices=("dag", "intake", "request"), help=t("ループ模式図または外部レビュー操作", "Loop diagram or external review operation"))
    review.add_argument("review_target", nargs="?", type=_path, help=t("intake 対象 report JSON", "intake report JSON"))
    review.add_argument("--runs", type=int, default=5, help=t("表示対象にする直近 run 数 (既定: 5)", "Number of recent runs to show (default: 5)"))
    review.add_argument("--repo", type=_path, default=Path("."), help=t("対象リポジトリ (既定: .)", "Target repository (default: .)"))
    review.add_argument("--section", choices=("results", "concerns", "premises"), help=t("表示するセクションだけに絞る", "Show only one section"))
    review.add_argument("--run", help=t("レビュー記録を関連付ける run ID", "Run ID to associate with the review"))
    review.add_argument("--triage", action="store_true", help=t("未確認項目をトリアージ表示", "Show unreviewed items for triage"))
    review.add_argument("--next", dest="next_item", action="store_true", help=t("次のトリアージ項目だけを表示", "Show only the next triage item"))
    review.add_argument("--full", action="store_true", help=t("完全なレビュー表示を要求", "Request the full review"))
    review.add_argument("--go", help=t("指定したカタログ項目の remediation を実行", "Execute remediation for a catalog item"))
    review.add_argument("--decision", help=t("判断 ID を記録", "Record a decision ID"))
    review.add_argument("--choice", choices=("go", "alt", "hold"), help=t("判断: go / alt / hold", "Decision: go / alt / hold"))
    review.add_argument("--format", choices=("text", "html", "json", "mermaid", "svg"), default="text", help=t("出力形式 (既定: text; dag は mermaid)", "Output format (default: text; mermaid for dag)"))
    review.add_argument("--out", help=t("dag 成果物の出力先 (reports 配下)", "dag output path (under reports)"))
    review.add_argument("--stage", choices=("intake", "retrieve", "act", "record", "memory", "audit", "handoff", "hooks", "learning"), help=t("dag 明細のステージ", "DAG detail stage"))
    review.add_argument("--check", help=t("dag 明細を検査 ID で絞り込み", "Filter DAG details by check ID"))

    status = sub.add_parser(
        "status", help=t("直近の Run Report と backlog を要約", "Summarize the latest Run Report and backlog"),
        description=t("対象リポジトリの最新状態、アラート、learning backlog を短く表示します。", "Briefly show repository state, alerts, and the learning backlog."),
        formatter_class=formatter,
    )
    status.add_argument("--repo", type=_path, default=Path("."), help=t("対象リポジトリ (既定: .)", "Target repository (default: .)"))

    hook = sub.add_parser(
        "hook", help=t("エージェント hook のイベントを処理", "Process an agent hook event"),
        description=t("標準入力の JSON hook イベントを正規化し、対応する hook 応答を JSON で出力します。", "Normalize a JSON hook event from stdin and print the hook response as JSON."),
        formatter_class=formatter,
    )
    hook.add_argument("platform", choices=("claude-code", "codex"), help=t("イベントを送信したプラットフォーム", "Platform that sent the event"))

    run = sub.add_parser("run", help=t("成果判定を検証・記録", "Verify and record run outcomes"), formatter_class=formatter)
    run_sub = run.add_subparsers(dest="run_command", required=True)
    verify = run_sub.add_parser("verify", help=t("宣言された受入条件を実行", "Execute declared acceptance checks"), formatter_class=formatter)
    verify.add_argument("--run", required=True)
    verify.add_argument("--repo", type=_path, default=Path("."))
    outcome = run_sub.add_parser("outcome", help=t("人間の成果ラベルを追記", "Append a human outcome label"), formatter_class=formatter)
    outcome.add_argument("--run", required=True)
    outcome.add_argument("--repo", type=_path, default=Path("."))
    outcome.add_argument("--status", choices=("pass", "fail"), required=True)
    outcome.add_argument("--note", required=True)
    stats = run_sub.add_parser("stats", help=t("ラン数・成果・統治コストを集計", "Summarize runs, outcomes, and governance overhead"), formatter_class=formatter)
    stats.add_argument("--repo", type=_path, default=Path("."))
    stats.add_argument("--windows", default="7d,28d")
    stats.add_argument("--now")

    doctor_cmd = sub.add_parser("doctor", help=t("ループ機構の健全性を検査", "Inspect loop health"), formatter_class=formatter)
    doctor_cmd.add_argument("--repo", type=_path, default=Path("."))
    doctor_cmd.add_argument("--fix", action="store_true")
    inbox_cmd = sub.add_parser("inbox", help=t("人間の非同期受信箱を表示", "Show the human async inbox"), formatter_class=formatter)
    inbox_cmd.add_argument("--repo", type=_path, default=Path("."))
    inbox_cmd.add_argument("--tui", action="store_true", help=t("TTY の対話画面", "Launch curses inbox UI"))
    inbox_cmd.add_argument("--interactive", action="store_true", help=t("行指向の対話画面", "Launch line-oriented inbox UI"))

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
                "kind": EVENT_OKF_APPLY, "report": str(args.report), "ok": bool(result.get("ok")),
                "touched": result.get("touched", []),
                "warnings": result.get("warnings", {}),
            })
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1

    if args.command == "okf" and args.okf_command == "query":
        if args.limit < 0:
            raise SystemExit("--limit must be non-negative")
        results = query_bundle(args.bundle, args.type_name, args.tag, args.grep, args.status, args.limit, args.tier, args.space)
        payload = {"results": results[:args.limit], "total_matched": len(results), "returned": min(len(results), args.limit)}
        if args.run:
            append_event(args.bundle.resolve().parent, args.run, {"kind": EVENT_RETRIEVAL, "query": " ".join(filter(None, [args.type_name, *args.tag, args.grep or ""])), "read_ids": [r["concept_id"] for r in results[:args.limit]]})
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "memory" and args.memory_command == "curate":
        if args.top < 0:
            raise SystemExit("--top must be non-negative")
        print(json.dumps(curate(args.repo, args.run, args.top), indent=2, ensure_ascii=False))
        return 0

    if args.command == "memory" and args.memory_command == "drafts":
        if args.drafts_command == "list":
            print(json.dumps(list_drafts(args.repo), indent=2, ensure_ascii=False))
        else:
            print(json.dumps(show_draft(args.repo, args.id), indent=2, ensure_ascii=False))
        return 0

    if args.command == "memory" and args.memory_command == "approve":
        if args.all and args.ids:
            raise SystemExit("memory approve: use --all or draft IDs, not both")
        print(json.dumps(approve(args.repo, args.ids, args.quote, args.run, args.all), indent=2, ensure_ascii=False))
        return 0

    if args.command == "memory" and args.memory_command == "reject":
        print(json.dumps(reject(args.repo, args.id, args.reason, args.run), indent=2, ensure_ascii=False))
        return 0

    if args.command == "memory" and args.memory_command == "snooze":
        print(json.dumps(snooze(args.repo, args.run, args.days), indent=2, ensure_ascii=False))
        return 0

    if args.command == "memory" and args.memory_command == "stats":
        windows = tuple(item.strip() for item in args.windows.split(",") if item.strip())
        stats = collect_stats(args.repo, args.bundle if args.bundle.is_absolute() else args.repo / args.bundle, windows, args.now, args.space)
        if args.format == "json":
            serializable = dict(stats)
            if serializable.get("coverage") is not None:
                serializable["coverage"] = serializable["coverage"].isoformat().replace("+00:00", "Z")
            print(json.dumps(serializable, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(render_stats(stats, windows), end="")
        return 0

    if args.command == "memory" and args.memory_command == "efficacy":
        windows = tuple(item.strip() for item in args.windows.split(",") if item.strip())
        print(render_efficacy(collect_efficacy(args.repo, windows, args.now, args.space)), end="")
        return 0

    if args.command == "learning" and args.learning_command == "promote":
        result = establish(args.repo.resolve(), args.establish) if args.establish is not None else promote(args.repo.resolve(), args.top, args.ids, args.type_name)
        if args.run:
            entries = result.get("drafts", []) if isinstance(result, dict) else result
            proposals = [concept for item in entries for concept in (item.get("concept_ids", [item.get("concept_id")]) if isinstance(item, dict) else []) if concept]
            append_event(args.repo.resolve(), args.run, {"kind": EVENT_MEMORY_DRAFT, "drafts": [item["draft"] for item in entries], "proposals": proposals})
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "okf" and args.okf_command == "draft":
        body = args.body_file.read_text(encoding="utf-8") if args.body_file else ""
        tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
        target, matches = make_draft(Path("."), args.type_name, args.concept_id, args.title, tags, body)
        print(json.dumps({"draft": str(target), "duplicate_candidates": matches}, indent=2, ensure_ascii=False))
        return 0

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

    if args.command == "audit" and args.audit_command == "export":
        print(str(export_packet(args.repo, args.run)))
        return 0

    if args.command == "review":
        from .review import execute_go, record_decision, render_review, render_review_html, render_triage, render_triage_html, record_review
        if args.runs < 0:
            raise SystemExit("--runs must be non-negative")
        if args.stage and args.review_view != "dag":
            raise SystemExit("--stage requires review dag")
        if args.check and not args.stage:
            raise SystemExit("--check requires --stage")
        if args.review_view == "intake":
            if args.review_target is None:
                raise SystemExit("review intake requires a report JSON path")
            result = intake(args.repo, args.review_target)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("accepted") else 1
        if args.review_view == "request":
            if args.run is None:
                raise SystemExit("review request requires --run")
            print(build_request(args.repo, args.run), end="")
            return 0
        if args.review_view == "dag":
            from .review_dag import DETAIL_GUIDE, render_dag, render_detail, render_summary, write_dag
            if args.stage:
                if args.format not in {"text", "json"}:
                    raise SystemExit("--stage supports only --format text or json")
                print(render_detail(args.repo.resolve(), args.stage, args.runs, check=args.check, as_json=args.format == "json"), end="")
                return 0
            fmt = args.format if args.format in {"mermaid", "svg", "html"} else "mermaid"
            content = render_dag(args.repo.resolve(), args.runs, run_id=args.run, fmt=fmt)
            write_dag(args.repo.resolve(), content, "mmd" if fmt == "mermaid" else fmt, args.out)
            if fmt in {"mermaid", "html"}:
                sys.stdout.write(content)
                if fmt == "mermaid":
                    sys.stdout.write(DETAIL_GUIDE + "\n")
            else:
                print(str((args.repo.resolve() / agent_root("state", "reports") / (args.out or "loop-dag.svg")).resolve()))
            return 0
        if args.go:
            print(execute_go(args.repo.resolve(), args.go, args.run), end="")
            return 0
        if args.decision:
            if not args.choice:
                raise SystemExit("--decision requires --choice")
            print(record_decision(args.repo.resolve(), args.decision, args.choice, args.run), end="")
            return 0
        if args.triage or args.next_item:
            if args.format == "html":
                print(render_triage_html(args.repo.resolve(), args.runs, next_item=args.next_item), end="")
            else:
                print(render_triage(args.repo.resolve(), args.runs, next_item=args.next_item, as_json=args.format == "json"), end="")
            return 0
        output = render_review_html(args.repo.resolve(), args.runs, args.section) if args.format == "html" else render_review(args.repo.resolve(), args.runs, args.section)
        print(output, end="")
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

    if args.command == "run" and args.run_command == "verify":
        print(json.dumps(verify_run(args.repo.resolve(), args.run), indent=2, ensure_ascii=False))
        return 0

    if args.command == "run" and args.run_command == "outcome":
        print(str(record_human_outcome(args.repo.resolve(), args.run, args.status, args.note)))
        return 0

    if args.command == "run" and args.run_command == "stats":
        windows = tuple(item.strip() for item in args.windows.split(",") if item.strip())
        print(render_run_stats(collect_run_stats(args.repo, windows, args.now)), end="")
        return 0

    if args.command == "doctor":
        print(json.dumps(doctor(args.repo, args.fix), indent=2, ensure_ascii=False))
        return 0

    if args.command == "inbox":
        if args.tui or args.interactive:
            from .inbox_model import interactive
            if args.interactive:
                return interactive(args.repo, sys.stdin, sys.stdout)
            try:
                import curses  # noqa: F401
                if not (sys.stdin.isatty() and sys.stdout.isatty()):
                    print("TTY unavailable; falling back to --interactive.")
                    return interactive(args.repo, sys.stdin, sys.stdout)
                from .inbox_tui import run
                from .inbox_model import start_session, end_session
                run_id = start_session(args.repo.resolve())
                try:
                    try:
                        run(args.repo.resolve(), run_id)
                    except KeyboardInterrupt:
                        print("\nInbox TUI interrupted; session closed.")
                finally:
                    end_session(args.repo.resolve(), run_id)
                from .audit.report import run_audit_report as run_tui_audit_report
                answer = input("Run audit now? [Y/n] ").strip().casefold()
                if answer not in {"n", "no"}:
                    print(f"audit: {run_tui_audit_report(args.repo.resolve(), run_id)}")
                return 0
            except ImportError:
                print("curses unavailable; falling back to --interactive.")
                return interactive(args.repo, sys.stdin, sys.stdout)
            except curses.error:
                print("curses unavailable; falling back to --interactive.")
                return interactive(args.repo, sys.stdin, sys.stdout)
        print(render_inbox(args.repo), end="")
        return 0

    raise SystemExit("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
