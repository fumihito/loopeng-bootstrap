from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..audit.policy import AUTONOMOUS_APPLIES_PER_RUN, AUTONOMOUS_NAMESPACES, AUTO_ESTABLISH, ESTABLISH_CITATIONS
from ..journal import EVENT_MEMORY_DRAFT, EVENT_OKF_APPLY, append_event
from .apply import apply_report
from .promote import promote
from .schema import load_report
from .schema import parse_frontmatter


def curate(repo: Path, run_id: str | None = None, top: int = AUTONOMOUS_APPLIES_PER_RUN) -> dict[str, Any]:
    """Promote learning once, then apply only the bounded safe subset."""
    repo = repo.resolve()
    run = run_id or "curate"
    # Draft generation may exceed the apply cap so excess candidates remain
    # visible as pending approval rather than disappearing from the run.
    promoted = promote(repo, max(0, top), autonomous=True)
    applied: list[str] = []
    pending: list[str] = []
    rejected: list[dict[str, str]] = []
    count = 0
    for item in promoted:
        report_path = Path(item["draft"])
        try:
            report = load_report(report_path)
            op = report.get("operations", [{}])[0]
            namespace = str(op.get("concept_id", "")).split("/", 1)[0]
            if namespace not in AUTONOMOUS_NAMESPACES or count >= AUTONOMOUS_APPLIES_PER_RUN:
                pending.append(str(report_path))
                append_event(repo, run, {"kind": EVENT_MEMORY_DRAFT, "draft": str(report_path), "status": "pending-approval"})
                continue
            result = apply_report(repo / "llmwiki", report_path, repo / ".agent-loop" / "runtime" / "okf-backups", autonomous=True)
            append_event(repo, run, {"kind": EVENT_OKF_APPLY, "report": str(report_path), "ok": bool(result.get("ok")), "touched": result.get("touched", []), "tier": "provisional", "actor": "autonomous-curate"})
            if result.get("ok"):
                applied.append(str(op.get("concept_id")))
                count += 1
            else:
                rejected.append({"draft": str(report_path), "error": "; ".join(str(x) for x in result.get("errors", []))})
        except Exception as exc:
            if "instruction smell" in str(exc):
                pending.append(str(report_path))
                append_event(repo, run, {"kind": EVENT_MEMORY_DRAFT, "draft": str(report_path), "status": "pending-approval", "reason": str(exc)})
            else:
                rejected.append({"draft": str(report_path), "error": str(exc)})
                append_event(repo, run, {"kind": EVENT_MEMORY_DRAFT, "draft": str(report_path), "status": "rejected", "error": str(exc)})
    established: list[str] = []
    if AUTO_ESTABLISH:
        # Citations are deliberately read from existing journal sidecars only;
        # no model judgement or current-run self-claim can establish a fact.
        citations: dict[str, int] = {}
        for journal in (repo / ".agent-loop" / "state" / "journal").glob("*.jsonl"):
            try:
                events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
            except (OSError, json.JSONDecodeError):
                continue
            for event in events:
                if event.get("kind") == "retrieval":
                    for concept_id in event.get("read_ids", []):
                        if isinstance(concept_id, str):
                            citations[concept_id] = citations.get(concept_id, 0) + 1
        report_sidecar = repo / ".agent-loop" / "state" / "reports" / f"{run}.json"
        safe_run = True
        try:
            safe_run = not bool(json.loads(report_sidecar.read_text(encoding="utf-8")).get("undeclared_critical"))
        except (OSError, json.JSONDecodeError):
            safe_run = False
        if safe_run:
            for path in (repo / "llmwiki").rglob("*.md"):
                if path.name in {"index.md", "log.md"}:
                    continue
                frontmatter, body = parse_frontmatter(path.read_text(encoding="utf-8"))
                concept_id = path.relative_to(repo / "llmwiki").with_suffix("").as_posix()
                if frontmatter.get("tier", "established") != "provisional" or citations.get(concept_id, 0) < ESTABLISH_CITATIONS:
                    continue
                frontmatter["tier"] = "established"
                rendered = ["---"] + [f"{key}: {json.dumps(value, ensure_ascii=False) if isinstance(value, (str, list)) else value}" for key, value in frontmatter.items()] + ["---", "", body.rstrip("\n"), ""]
                report = {"schema": "okf-report-v1", "role": "auto-establish", "authority": "policy", "operations": [{"action": "UPSERT", "proposal_id": f"auto-establish-{concept_id.replace('/', '-')}", "concept_id": concept_id, "document": "\n".join(rendered)}]}
                target = repo / ".agent-loop" / "state" / "memory-drafts" / f"auto-establish-{concept_id.replace('/', '-')}.json"
                target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                result = apply_report(repo / "llmwiki", target, repo / ".agent-loop" / "runtime" / "okf-backups")
                append_event(repo, run, {"kind": EVENT_OKF_APPLY, "report": str(target), "ok": bool(result.get("ok")), "touched": result.get("touched", []), "tier": "established", "actor": "auto-establish"})
                if result.get("ok"):
                    established.append(concept_id)
    result = {"promoted": promoted, "applied": applied, "established": established, "pending": pending, "rejected": rejected}
    (repo / ".agent-loop" / "state" / "last-curate.json").parent.mkdir(parents=True, exist_ok=True)
    (repo / ".agent-loop" / "state" / "last-curate.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result
