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
        if not isinstance(requirement, dict):
            requirement = {}
        legacy_due = any(isinstance(alert, dict) and alert.get("check_id") == "external_review_due" for alert in sidecar.get("alerts", [])) if isinstance(sidecar, dict) else False
        if (isinstance(requirement, dict) and requirement.get("due")) or legacy_due:
            due += 1
            # Legacy reports predate review_requirement; retain the same
            # every-fifth calibration obligation while migrating them.
            required_external += int(
                requirement.get("relation") == "external"
                or (not requirement and due % 5 == 0)
            )
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
    # Compare accepted reviews on the same run: external-only fail findings
    # are the observable counterexample signal for the three-review rule.
    journal_root = repo.resolve() / agent_root("state", "journal")
    self_pass: dict[str, set[str]] = defaultdict(set)
    external_fail: dict[str, set[str]] = defaultdict(set)
    for journal in journal_root.glob("*.jsonl") if journal_root.is_dir() else ():
        try:
            events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError):
            continue
        for event in events:
            if not isinstance(event, dict) or event.get("kind") != "external-review" or event.get("accepted_by") != "loopeng review intake":
                continue
            relation = event.get("relation")
            for dimension in event.get("dimensions", []) if isinstance(event.get("dimensions"), list) else ():
                if not isinstance(dimension, dict):
                    continue
                identifier = str(dimension.get("id"))
                if relation == "self-family" and dimension.get("verdict") == "pass":
                    self_pass[journal.stem].add(identifier)
                if relation == "external" and dimension.get("verdict") == "fail":
                    external_fail[journal.stem].add(identifier)
    counterexamples = sum(len(self_pass[run] & external_fail[run]) for run in self_pass)
    return {"due": due, "required_external": required_external,
            "by_relation": normalized, "self_family_only_findings": dict(unique_only),
            "counterexample_window": {"required": 3, "observed": counterexamples}}


def render(repo: Path) -> str:
    value = summarize(repo)
    lines = ["Review calibration", f"due={value['due']} required_external={value['required_external']}"]
    for relation, metrics in sorted(value["by_relation"].items()):
        lines.append(f"{relation}: total={metrics['total']} fail={metrics['fail']} unable={metrics['unable']}")
        for dimension, values in sorted(metrics.get("dimensions", {}).items()):
            lines.append(f"  {dimension}: fail={values['fail']} unable={values['unable']} / {values['total']}")
    lines.append("self-family-only findings: " + (json.dumps(value["self_family_only_findings"], sort_keys=True) if value["self_family_only_findings"] else "none"))
    observed = value["counterexample_window"]["observed"]
    lines.append(f"counterexample window: {observed}/3 observed")
    return "\n".join(lines) + "\n"
