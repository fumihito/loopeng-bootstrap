from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .review_request import resolve_packet

OUT_NAME = "_out"
EVIDENCE_MAX_LINES = 8


def out_root(repo: Path) -> Path:
    return repo.resolve() / OUT_NAME


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default


def _packet(repo: Path, run_id: str) -> Path:
    packet = resolve_packet(repo, run_id)
    if packet is None:
        raise FileNotFoundError(f"review packet not found for run {run_id}")
    return packet.resolve()


def _contract(repo: Path, run_id: str, packet_hash: str) -> dict[str, Any] | None:
    root = repo / agent_root("state", "reviews")
    for path in sorted(root.rglob("*.json")) if root.is_dir() else ():
        value = _read_json(path)
        packet = value.get("packet") if isinstance(value, dict) else None
        if isinstance(packet, dict) and packet.get("run_id") == run_id and packet.get("packet_hash") == packet_hash:
            return value
    return None


def _text(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _pre(value: Any) -> str:
    return f"<pre>{_text(value)}</pre>"


def _page(title: str, body: str) -> str:
    return """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>%s</title>
<style>
body{margin:0;background:#111827;color:#e5e7eb;font:15px/1.5 system-ui,sans-serif}main{max-width:1180px;margin:0 auto;padding:2rem}h1,h2{color:#f9fafb}section{background:#1f2937;border:1px solid #374151;border-radius:.6rem;padding:1rem;margin:1rem 0}pre{white-space:pre-wrap;overflow:auto;background:#111827;padding:.8rem;border-radius:.4rem}table{border-collapse:collapse;width:100%%}th,td{padding:.55rem;text-align:left;vertical-align:top;border-bottom:1px solid #4b5563}.pass{color:#86efac}.fail{color:#fca5a5}.unable{color:#fde68a}.critical{background:#7f1d1d}.ok{background:#14532d}a{color:#93c5fd}
</style></head><body><main>%s</main></body></html>
""" % (_text(title), body)


def _write_file_pages(root: Path, packet: Path, names: list[str]) -> dict[str, str]:
    links: dict[str, str] = {}
    files_root = root / "files"
    for name in names:
        source = (packet / name).resolve()
        try:
            source.relative_to(packet.resolve())
        except ValueError:
            continue
        if not source.is_file():
            continue
        relative = Path(name)
        target = files_root / (str(relative).replace("/", "__") + ".html")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            content = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            content = f"unreadable: {type(exc).__name__}"
        target.write_text(_page(name, f"<h1>{_text(name)}</h1>{_pre(content)}"), encoding="utf-8")
        links[name] = "files/" + target.name
    return links


def _evidence(packet: Path, ref: str) -> str:
    parts = ref.split(":")
    if ref.startswith("journal:") and len(parts) == 3:
        events = _read_json(packet / "journal.json", [])
        try:
            line = int(parts[2])
            value = events[line - 1] if isinstance(events, list) and 1 <= line <= len(events) else None
        except ValueError:
            value = None
        return json.dumps(value, ensure_ascii=False, indent=2) if value is not None else "unresolved evidence"
    if ref.startswith("file:") and len(parts) == 3:
        relative = parts[1]
        source = (packet / "source" / relative).resolve()
        try:
            line = int(parts[2])
            source.relative_to((packet / "source").resolve())
            lines = source.read_text(encoding="utf-8").splitlines()
            start = max(1, line - 2)
            return "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, min(len(lines), line + 5) + 1))
        except (ValueError, OSError, UnicodeError):
            return "unresolved evidence"
    return "unresolved evidence"


def render_review(repo: Path, run_id: str) -> Path:
    repo = repo.resolve()
    packet = _packet(repo, run_id)
    manifest = _read_json(packet / "manifest.json", {})
    sidecars = [name for name in manifest.get("files", []) if isinstance(name, str) and name.endswith(".json") and name not in {"manifest.json", "journal.json", "source-index.json"}]
    sidecar = _read_json(packet / sidecars[0], {}) if sidecars else {}
    contract = _contract(repo, run_id, str(manifest.get("packet_hash", "")))
    report = _read_json(packet / f"{run_id}.json", {})
    output = out_root(repo) / "review" / run_id
    output.mkdir(parents=True, exist_ok=True)
    names = [name for name in manifest.get("files", []) if isinstance(name, str)]
    if "manifest.json" not in names:
        names.insert(0, "manifest.json")
    links = _write_file_pages(output, packet, names)
    dag = repo / agent_root("state", "reports") / "loop-dag.svg"
    dag_link = None
    if dag.is_file():
        try:
            from .review_dag import render_dag
            (output / "loop-dag.svg").write_text(render_dag(repo, run_id=run_id, fmt="svg"), encoding="utf-8")
        except (OSError, ValueError):
            shutil.copyfile(dag, output / "loop-dag.svg")
        dag_link = "loop-dag.svg"
    agent = report.get("agent", sidecar.get("agent", "unknown"))
    goal = report.get("goal", sidecar.get("goal", "unknown"))
    outcome = sidecar.get("outcome", report.get("outcome", "unknown"))
    alerts = sidecar.get("alerts", []) if isinstance(sidecar.get("alerts"), list) else []
    critical = any(isinstance(item, dict) and item.get("severity") == "critical" for item in alerts)
    dimensions = contract.get("dimensions", []) if contract else []
    rows = []
    for item in dimensions:
        if not isinstance(item, dict):
            continue
        verdict = str(item.get("verdict", "unable"))
        evidence = item.get("evidence", []) if isinstance(item.get("evidence"), list) else []
        evidence_html = []
        for pointer in evidence:
            if isinstance(pointer, dict):
                ref = str(pointer.get("ref", ""))
                evidence_html.append(f"<details><summary>{_text(ref)}</summary>{_pre(_evidence(packet, ref))}</details>")
        rows.append(f"<tr><th>{_text(item.get('id'))}</th><td class=\"{_text(verdict)}\">{_text(verdict)}</td><td>{len(evidence)}</td><td>{_text(item.get('note', ''))}{''.join(evidence_html)}</td></tr>")
    findings = contract.get("findings", []) if contract else []
    findings_html = "".join(_pre(item) for item in findings) or "<p>none</p>"
    manifest_link = links.get("manifest.json", "")
    body = f"<h1>Review {_text(run_id)}</h1><p>agent: {_text(agent)}<br>goal: {_text(goal)}<br>outcome: {_text(outcome)}</p><p class=\"{'critical' if critical else 'ok'}\">{'critical alerts present' if critical else 'no critical alerts'}</p>"
    body += "<section><h2>Dimensions</h2><table><tr><th>ID</th><th>Verdict</th><th>Evidence</th><th>Note / resolved evidence</th></tr>" + "".join(rows) + "</table></section>"
    body += f"<section><h2>Findings</h2>{findings_html}</section>"
    if dag_link:
        body += f'<section><h2>DAG</h2><img src="{_text(dag_link)}" alt="loop DAG"></section>'
    body += f"<section><h2>Packet</h2><p><a href=\"{_text(manifest_link)}\">manifest.json</a></p>" + " ".join(f'<a href="{_text(link)}">{_text(name)}</a>' for name, link in sorted(links.items()) if name != "manifest.json") + "</section>"
    target = output / "index.html"
    target.write_text(_page(f"Review {run_id}", body), encoding="utf-8")
    return target


def render_index(repo: Path) -> Path:
    repo = repo.resolve()
    root = out_root(repo)
    review_root = root / "review"
    rows = []
    if review_root.is_dir():
        for path in sorted(review_root.iterdir()):
            if (path / "index.html").is_file():
                stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
                rows.append(f'<li><a href="review/{_text(path.name)}/">{_text(path.name)}</a> — {_text(stamp)}</li>')
    root.mkdir(parents=True, exist_ok=True)
    target = root / "index.html"
    target.write_text(_page("Loop Reviews", "<h1>Loop Reviews</h1><ul>" + "".join(rows) + "</ul>"), encoding="utf-8")
    return target
