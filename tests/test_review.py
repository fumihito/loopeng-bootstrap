from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from loopeng._paths import agent_root
from loopeng.okf.schema import validate_document_text
from loopeng.review import execute_go, record_decision, render_review, render_triage
from loopeng.review_dag import STAGE_MAP, render_dag, write_dag


def sidecar(root: Path, run_id: str, *, check: str | None = None, alerts: list[dict] | None = None, undeclared: bool = False, ended: str | None = None) -> None:
    report_dir = root / agent_root("state", "reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "agent": "test",
        "goal": run_id,
        "started_at": ended or "2026-07-12T00:00:00+00:00",
        "ended_at": ended or "2026-07-12T00:01:00+00:00",
        "alerts": alerts if alerts is not None else ([{"check_id": check, "severity": "warn", "declared": True}] if check else []),
        "undeclared_critical": undeclared,
        "memory": {"applied": 1, "rejected": 0},
        "handoff_written": True,
        "schema": 1,
    }
    (report_dir / f"{run_id}.json").write_text(json.dumps(report), encoding="utf-8")


class ReviewTests(unittest.TestCase):
    def test_dag_fixture_maps_alerts_and_classes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1", alerts=[
                *([{"check_id": "protected_path_mutation", "severity": "critical", "declared": False}] * 15),
                {"check_id": "protected_path_mutation", "severity": "critical", "declared": True},
                *([{"check_id": "journal_coverage", "severity": "critical", "declared": True}] * 18),
                *([{"check_id": "learning_backlog", "severity": "warn", "declared": True}] * 19),
            ])
            (root / agent_root("state", "handoff.json")).parent.mkdir(parents=True, exist_ok=True)
            (root / agent_root("state", "handoff.json")).write_text('{"source_turn_id":"r1"}', encoding="utf-8")
            text = render_dag(root, fmt="mermaid")
            self.assertIn('act["act<br/>✖ 15 / ⚠ 1"]', text)
            self.assertIn('record["record<br/>⚠ 18"]', text)
            self.assertIn('learning["learning<br/>⚠ 19"]', text)
            self.assertIn('handoff["handoff<br/>⚠ unconsumed"]', text)

    def test_dag_is_deterministic_and_svg_is_xml(self) -> None:
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1")
            first = render_dag(root)
            second = render_dag(root)
            self.assertEqual(first, second)
            svg = render_dag(root, fmt="svg")
            ET.fromstring(svg)
            self.assertIn("Legend:", svg)
            write_dag(root, svg, "svg")
            self.assertEqual((root / agent_root("state", "reports") / "loop-dag.svg").read_text(encoding="utf-8"), svg)

    def test_dag_unmapped_and_run_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1", alerts=[{"check_id": "new_check", "severity": "warn", "declared": True}])
            journal = root / agent_root("state", "journal")
            journal.mkdir(parents=True)
            journal.joinpath("r1.jsonl").write_text("\n".join(json.dumps({"kind": kind}) for kind in ("run-start", "intent", "run-end")) + "\n", encoding="utf-8")
            text = render_dag(root, run_id="r1")
            self.assertIn('event0["1: run-start"]', text)
            self.assertIn('event2["3: run-end"]', text)
            self.assertNotIn('event3[', text)
            self.assertIn("unmapped", text)

    def test_stage_map_covers_registered_checks(self) -> None:
        from loopeng.audit.checks import CHECKS
        for check in CHECKS:
            check_id = check.__name__.removeprefix("check_")
            self.assertIn(check_id, STAGE_MAP)

    def test_results_are_sidecar_only_and_limited(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for index in range(6):
                sidecar(root, f"run-{index}", ended=f"2026-07-12T00:0{index}:00+00:00")
            text = render_review(root)
            self.assertIn("Scope: last 5 of 5 runs with sidecar", text)
            self.assertIn("run-5", text)
            self.assertNotIn("run-0", text)

    def test_recurring_threshold_is_three_runs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for index in range(5):
                sidecar(root, f"run-{index}", check="budget_exceeded" if index < 3 else None, ended=f"2026-07-12T00:0{index}:00+00:00")
            self.assertIn("[RECURRING] budget_exceeded", render_review(root, 5))
            (root / agent_root("state", "reports") / "run-2.json").unlink()
            self.assertNotIn("[RECURRING] budget_exceeded", render_review(root, 5))

    def test_premises_markers_and_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            decisions = root / "llmwiki" / "decisions"
            constraints = root / "llmwiki" / "constraints"
            decisions.mkdir(parents=True)
            constraints.mkdir(parents=True)
            base = '''---
type: "Decision"
title: "{title}"
description: "test"
tags: [{tags}]
timestamp: "2026-01-01T00:00:00Z"
status: "{status}"
sensitivity: "internal"
authority: "test"
confidence: "1.0"
{extra}---

# Invalidation
If the observed condition changes.
'''
            (decisions / "due.md").write_text(base.format(title="Due", tags='"x"', status="active", extra='review_after: "2020-01-01"\n'), encoding="utf-8")
            (decisions / "pending.md").write_text(base.format(title="Pending", tags='"pending-decision"', status="active", extra=""), encoding="utf-8")
            (constraints / "deprecated.md").write_text(base.format(title="Old", tags='"x"', status="deprecated", extra=""), encoding="utf-8")
            text = render_review(root, section="premises")
            self.assertIn("[DUE]", text)
            self.assertIn("[PENDING]", text)
            self.assertIn("If the observed condition changes.", text)
            self.assertNotIn("deprecated", text)

    def test_review_after_validation(self) -> None:
        valid = '''---
type: "Decision"
title: "D"
description: "d"
tags: ["x"]
timestamp: "2026-01-01"
status: "active"
sensitivity: "internal"
authority: "test"
confidence: "1.0"
review_after: "2026-07-01"
---
# D
'''
        invalid = valid.replace('"2026-07-01"', '"not-a-date"')
        self.assertEqual(validate_document_text(valid), [])
        self.assertTrue(any("review_after" in error for error in validate_document_text(invalid)))

    def test_audit_writes_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            journal = root / agent_root("state", "journal")
            journal.mkdir(parents=True)
            events = [
                {"kind": "run-start", "agent": "codex", "goal": "test", "timestamp": "2026-07-12T00:00:00+00:00"},
                {"kind": "run-end", "timestamp": "2026-07-12T00:01:00+00:00"},
            ]
            (journal / "r1.jsonl").write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")
            subprocess.run([sys.executable, "-m", "loopeng", "audit", "run", "--run", "r1", "--repo", str(root)], check=True, capture_output=True, text=True)
            payload = json.loads((root / agent_root("state", "reports") / "r1.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], 1)
            self.assertEqual(payload["goal"], "test")

    def test_triage_groups_cooccurring_known_members(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for index in range(3):
                sidecar(root, f"r{index}", alerts=[{"check_id": "journal_coverage", "severity": "critical"}, {"check_id": "protected_path_mutation", "severity": "critical"}], undeclared=True)
            text = render_triage(root)
            self.assertIn("hooks-absence", text)
            self.assertIn("grouped into 1 items", text)

    def test_triage_does_not_group_independent_members(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1", alerts=[{"check_id": "journal_coverage", "severity": "critical"}], undeclared=False)
            sidecar(root, "r2", alerts=[{"check_id": "protected_path_mutation", "severity": "critical"}], undeclared=True)
            text = render_triage(root)
            self.assertNotIn("hooks-absence", text)
            self.assertIn("review: next", text)
            self.assertIn("grouped into 2 items", text)
            self.assertIn("journal_coverage", render_triage(root, next_item=True))

    def test_triage_cursor_and_digest_reset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1", alerts=[{"check_id": "budget_exceeded", "severity": "warn"}])
            sidecar(root, "r2", alerts=[{"check_id": "intent_overdeclaration", "severity": "warn"}])
            first = render_triage(root)
            second = render_triage(root, next_item=True)
            self.assertIn("budget-recurrence", first)
            self.assertIn("intent-overdeclaration", second)
            sidecar(root, "r3", alerts=[{"check_id": "budget_exceeded", "severity": "warn"}])
            reset = render_triage(root)
            self.assertIn("budget-recurrence", reset)

    def test_catalog_miss_and_non_executable_go(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1", alerts=[{"check_id": "new_check", "severity": "critical"}])
            self.assertIn("catalog-miss:new_check", render_triage(root))
            result = execute_go(root, "catalog-miss:new_check")
            self.assertIn("実行せず停止", result)
            journal = next((root / agent_root("state", "journal")).glob("review-go-*.jsonl"))
            self.assertIn('"kind": "decision"', journal.read_text(encoding="utf-8"))

    def test_learning_go_writes_proposal_without_apply_and_hold_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            learning = root / agent_root("state", "learning")
            learning.mkdir(parents=True)
            (learning / "one.json").write_text("{}", encoding="utf-8")
            sidecar(root, "r1", alerts=[{"check_id": "learning_backlog", "severity": "info"}])
            result = execute_go(root, "learning-backlog")
            self.assertIn("apply はしていません", result)
            self.assertTrue(list((root / agent_root("state", "review-proposals")).glob("*.md")))
            self.assertEqual(list((root / agent_root("state", "review-proposals")).glob("*.md"))[0].read_text(encoding="utf-8").count("apply"), 0)
            record_decision(root, "learning-backlog", "hold")
            self.assertIn("[HELD]", render_triage(root))
