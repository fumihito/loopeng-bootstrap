"""Calibration metrics for external and self-family review evidence."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ._paths import agent_root


def summarize(repo: Path) -> dict[str, Any]:
    reports = repo.resolve() / agent_root("state", "reports")
    rates: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0, "fail": 0, "unable": 0, "dimensions": defaultdict(lambda: {"total": 0, "fail": 0, "unable": 0})})
    unique_only = Counter()
    due = 0
    required_external = 0
    for path in reports.glob("*.json") if reports.is_dir() else ():
        try:
            sidecar = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        requirement = sidecar.get("review_requirement") if isinstance(sidecar, dict) else {}
        if isinstance(requirement, dict) and requirement.get("due"):
            due += 1
            required_external += int(requirement.get("relation") == "external")
        review = sidecar.get("review") if isinstance(sidecar, dict) else None
        if not isinstance(review, dict):
            continue
        relation = str(review.get("relation") or "external")
        for dimension in review.get("dimensions", []) if isinstance(review.get("dimensions"), list) else ():
            if not isinstance(dimension, dict):
                continue
            bucket = rates[relation]
            bucket["total"] += 1
            bucket["fail"] += int(dimension.get("verdict") == "fail")
            bucket["unable"] += int(dimension.get("verdict") == "unable")
            dim = bucket["dimensions"][str(dimension.get("id") or "unknown")]
            dim["total"] += 1
            dim["fail"] += int(dimension.get("verdict") == "fail")
            dim["unable"] += int(dimension.get("verdict") == "unable")
        for finding in review.get("findings", []) if isinstance(review.get("findings"), list) else ():
            if isinstance(finding, dict) and finding.get("self_family_only"):
                unique_only[str(finding.get("dimension") or "unknown")] += 1
    normalized = {relation: {**metrics, "dimensions": dict(metrics["dimensions"])} for relation, metrics in rates.items()}
    return {"due": due, "required_external": required_external,
            "by_relation": normalized, "self_family_only_findings": dict(unique_only),
            "counterexample_window": {"required": 3, "observed": 0}}


def render(repo: Path) -> str:
    value = summarize(repo)
    lines = ["Review calibration", f"due={value['due']} required_external={value['required_external']}"]
    for relation, metrics in sorted(value["by_relation"].items()):
        lines.append(f"{relation}: total={metrics['total']} fail={metrics['fail']} unable={metrics['unable']}")
        for dimension, values in sorted(metrics.get("dimensions", {}).items()):
            lines.append(f"  {dimension}: fail={values['fail']} unable={values['unable']} / {values['total']}")
    lines.append("self-family-only findings: " + (json.dumps(value["self_family_only_findings"], sort_keys=True) if value["self_family_only_findings"] else "none"))
    lines.append("counterexample window: 0/3 observed")
    return "\n".join(lines) + "\n"
