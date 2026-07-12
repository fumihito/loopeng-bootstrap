from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from loopeng._paths import agent_root
from loopeng.audit.report import run_audit_report
from loopeng.journal import append_event
from loopeng.okf.schema import validate_document_text
from loopeng.review import execute_go, record_decision, render_review, render_triage
from loopeng.review_dag import STAGE_MAP, _badge, render_dag, render_detail, render_summary, write_dag


def sidecar(root: Path, run_id: str, *, check: str | None = None, alerts: list[dict] | None = None, undeclared: bool = False, ended: str | None = None, schema: int = 1) -> None:
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
        "schema": schema,
    }
    (report_dir / f"{run_id}.json").write_text(json.dumps(report), encoding="utf-8")


class ReviewTests(unittest.TestCase):
    def test_dag_fixture_maps_alerts_and_classes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1", alerts=[
                {"check_id": "protected_path_mutation", "severity": "critical", "declared": False},
                {"check_id": "protected_path_mutation", "severity": "critical", "declared": True},
                {"check_id": "journal_coverage", "severity": "critical"},
                {"check_id": "secret_persistence", "severity": "critical", "declared": True},
                *([{"check_id": "learning_backlog", "severity": "warn", "declared": True}] * 19),
            ])
            (root / agent_root("state", "handoff.json")).parent.mkdir(parents=True, exist_ok=True)
            (root / agent_root("state", "handoff.json")).write_text('{"source_turn_id":"r1"}', encoding="utf-8")
            text = render_dag(root, fmt="mermaid")
            self.assertIn('act["act<br/>✖ 1 / ⚠ 1"]', text)
            self.assertIn('record["record<br/>✖ 2"]', text)
            self.assertIn('learning["learning<br/>⚠ 19"]', text)
            self.assertIn('handoff["handoff<br/>⚠ unconsumed"]', text)
            self.assertIn("class act,record crit;", text)

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
            self.assertIn("Legend: ✖ critical (undeclared)  /  ⚠ warn or declared  /  ✔ no alert", svg)
            self.assertIn('marker id="arrowhead"', svg)
            self.assertIn('stroke-dasharray="6 4"', svg)
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

            sidecar(root, "r2", alerts=[
                {"check_id": "new_check", "severity": "warn"},
                {"check_id": "another_new_check", "severity": "critical"},
            ])
            self.assertIn('unmapped["unmapped<br/>⚠ 3:', render_dag(root))

    def test_dag_render_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1", alerts=[{"check_id": "journal_coverage", "severity": "critical"}])
            snapshot = sorted(
                (path.relative_to(root), path.read_bytes())
                for path in root.rglob("*")
                if path.is_file()
            )
            render_dag(root)
            self.assertEqual(
                snapshot,
                sorted(
                    (path.relative_to(root), path.read_bytes())
                    for path in root.rglob("*")
                    if path.is_file()
                ),
            )

    def test_dag_detail_schema_two_is_sorted_and_uses_correct_buckets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            long_message = "m" * 205
            sidecar(root, "20260711-1802", schema=2, alerts=[
                {"check_id": "protected_path_mutation", "severity": "critical", "declared": True, "message": "declared", "paths": ["a.py"]},
                {"check_id": "journal_coverage", "severity": "critical", "message": long_message, "paths": [f"path-{i}.py" for i in range(12)], "paths_total": 12},
            ])
            sidecar(root, "20260712-0930", schema=2, alerts=[
                {"check_id": "journal_coverage", "severity": "critical", "message": "latest", "paths": ["latest.py"]},
            ])
            text = render_detail(root, "record")
            self.assertIn("stage: record — findings: 2 (✖ 2) across 2 runs", text)
            self.assertLess(text.index("20260712-0930"), text.index("20260711-1802"))
            self.assertIn("✖ critical", text)
            self.assertNotIn("⚠ critical", text)
            self.assertIn("(+5 more)", text)
            self.assertIn("(+2 more)", text)

            act = render_detail(root, "act")
            self.assertIn("⚠ warn", act)

    def test_dag_detail_accepts_schema_one_with_unavailable_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1", alerts=[{"check_id": "journal_coverage", "severity": "critical"}])
            text = render_detail(root, "record")
            self.assertIn("(schema 1 sidecar — detail unavailable)", text)

    def test_dag_detail_limits_findings_and_supports_check_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1", schema=2, alerts=[
                {"check_id": "journal_coverage", "severity": "critical", "message": str(index)}
                for index in range(31)
            ])
            text = render_detail(root, "record", check="journal_coverage")
            self.assertIn("findings: 31", text)
            self.assertIn("showing first 30 of 31", text)
            self.assertEqual(text.count("run r1"), 30)
            self.assertIn("(no findings)", render_detail(root, "record", check="secret_persistence"))

    def test_dag_detail_handoff_entry_and_json_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            handoff = root / agent_root("state", "handoff.json")
            handoff.parent.mkdir(parents=True, exist_ok=True)
            handoff.write_text(json.dumps({"source_turn_id": "r1", "generated_at": "2026-07-12T00:00:00Z"}), encoding="utf-8")
            first = render_detail(root, "handoff", as_json=True)
            second = render_detail(root, "handoff", as_json=True)
            self.assertEqual(first, second)
            payload = json.loads(first)
            self.assertEqual(payload["items"][0]["run_id"], "r1")
            self.assertIn("generated_at", payload["items"][0]["message"])

    def test_dag_detail_is_read_only_and_invalid_stage_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            before = sorted((p.relative_to(root), p.read_bytes()) for p in root.rglob("*") if p.is_file())
            self.assertEqual(render_detail(root, "act"), render_detail(root, "act"))
            after = sorted((p.relative_to(root), p.read_bytes()) for p in root.rglob("*") if p.is_file())
            self.assertEqual(before, after)
            with self.assertRaisesRegex(ValueError, r"valid stages: intake\|retrieve\|act"):
                render_detail(root, "invalid")

    def test_audit_schema_two_secret_message_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            append_event(root, "r1", {"kind": "run-start", "agent": "test", "goal": "secret test"})
            append_event(root, "r1", {"kind": "note", "message": "password=SUPER-SECRET-VALUE"})
            append_event(root, "r1", {"kind": "run-end"})
            run_audit_report(root, "r1")
            payload = json.loads((root / agent_root("state", "reports") / "r1.json").read_text(encoding="utf-8"))
            encoded = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("SUPER-SECRET-VALUE", encoded)
            self.assertEqual(payload["schema"], 2)
            self.assertTrue(any(alert["check_id"] == "secret_persistence" for alert in payload["alerts"]))

    def test_dag_run_truncates_after_sixty_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1")
            journal = root / agent_root("state", "journal")
            journal.mkdir(parents=True)
            journal.joinpath("r1.jsonl").write_text(
                "\n".join(json.dumps({"kind": f"event-{index}"}) for index in range(61)) + "\n",
                encoding="utf-8",
            )
            text = render_dag(root, run_id="r1")
            self.assertIn("events: 61", text)
            self.assertIn('truncated["… truncated after 60 events"]', text)
            self.assertIn('event59["60: event-59"]', text)
            self.assertNotIn('event60["61: event-60"]', text)

    def test_dag_summary_is_explicit_when_alert_free(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(render_summary(Path(td)), "DAG alerts: none")

    def test_dag_handoff_does_not_hide_critical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sidecar(root, "r1", alerts=[{"check_id": "hook_failure", "severity": "critical"}])
            handoff = root / agent_root("state", "handoff.json")
            handoff.parent.mkdir(parents=True, exist_ok=True)
            handoff.write_text('{"source_turn_id":"r1"}', encoding="utf-8")
            self.assertEqual(_badge("handoff", {"handoff": 1}, {"handoff": 1}, handoff_unconsumed=True), "✖ 1 / ⚠ unconsumed")

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
            self.assertEqual(payload["schema"], 2)
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
