from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from ._paths import wiki_space
from .okf.schema import parse_document

STATS_WINDOWS = ("1d", "3d", "7d", "28d")


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _sort_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter, key=lambda item: (-counter[item], item))}


def _read_log(bundle: Path) -> list[dict[str, Any]]:
    path = bundle / "log.jsonl"
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("v") == 1:
            try:
                _parse_time(str(value["ts"]))
            except (KeyError, TypeError, ValueError):
                continue
            entries.append(value)
    return entries


def _commit_count(repo: Path, cutoff: datetime, bundle: Path) -> int:
    try:
        relative_bundle = bundle.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        relative_bundle = bundle.name
    proc = subprocess.run(
        ["git", "-C", str(repo), "log", f"--since={cutoff.isoformat()}", "--oneline", "--", ".", f":(exclude){relative_bundle}/**", f":(exclude){relative_bundle}"],
        text=True, capture_output=True, check=False,
    )
    return sum(1 for line in proc.stdout.splitlines() if line.strip())


def collect_stats(repo: Path, bundle: Path, windows: tuple[str, ...] = STATS_WINDOWS, now: str | datetime | None = None, space: str = "current") -> dict[str, Any]:
    repo, bundle = repo.resolve(), bundle.resolve()
    as_of = _parse_time(now) if isinstance(now, str) else (now or datetime.now(timezone.utc))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    entries = _read_log(bundle)
    current, _ = wiki_space(repo)
    selected_space = current if space == "current" else space
    if selected_space != "all":
        entries = [item for item in entries if str(item.get("space") or selected_space) == selected_space]
    result: dict[str, Any] = {"coverage": min((_parse_time(str(item["ts"])) for item in entries), default=None), "windows": {}}
    for label in windows:
        if label not in STATS_WINDOWS:
            raise ValueError(f"unsupported window: {label}")
        days = int(label[:-1])
        cutoff = as_of - timedelta(days=days)
        selected = [item for item in entries if cutoff <= _parse_time(str(item["ts"])) <= as_of]
        counters = {key: Counter(str(item.get(key) or "unknown") for item in selected) for key in ("action", "namespace", "type", "tier", "author", "space")}
        result["windows"][label] = {
            "ops": len(selected),
            "commits": _commit_count(repo, cutoff, bundle),
            "by": {key: _sort_counts(counters[key]) for key in ("action", "namespace", "type", "tier", "author")},
            "by_space": _sort_counts(counters["space"]),
        }
    divergence = []
    seven = result["windows"].get("7d")
    if entries and seven:
        if seven["commits"] >= 8 and seven["ops"] == 0:
            divergence.append({"rule": "A", "severity": "warn", "commits": seven["commits"], "ops": seven["ops"]})
        if seven["ops"] >= 8 and seven["commits"] == 0:
            divergence.append({"rule": "B", "severity": "info", "commits": seven["commits"], "ops": seven["ops"]})
    result["divergence"] = divergence
    return result


def _compact(values: dict[str, int]) -> str:
    return ", ".join(f"{key} {value}" for key, value in values.items()) or "-"


def render_stats(stats: dict[str, Any], windows: tuple[str, ...]) -> str:
    coverage = stats.get("coverage")
    coverage_text = f"since {coverage.date().isoformat()}" if isinstance(coverage, datetime) else "no memory log yet"
    lines = ["[loopeng-bootstrap v0.2.0 | loopeng/v0.2 | memory-stats]", f"Memory updates (log coverage {coverage_text})", "", "window  ops  upsert  deprecate  by namespace              by tier          by author  by space"]
    for label in windows:
        item = stats["windows"][label]
        action = item["by"]["action"]
        lines.append(f"{label:<7} {item['ops']:>3}  {action.get('UPSERT', 0):>6}  {action.get('DEPRECATE', 0):>9}  {_compact(item['by']['namespace']):<24} {_compact(item['by']['tier']):<16} {_compact(item['by']['author']):<18} {_compact(item.get('by_space', {}))}")
    commits = " / ".join(f"{label} {stats['windows'][label]['commits']}" for label in windows)
    lines.extend(["", f"Commits (non-llmwiki): {commits}"])
    divergence = stats.get("divergence", [])
    health = "OK (no divergence rule triggered)" if not divergence else "; ".join(f"{item['severity']} rule {item['rule']} (ops {item['ops']}, commits {item['commits']})" for item in divergence)
    lines.append(f"Health: {health}")
    return "\n".join(lines) + "\n"
