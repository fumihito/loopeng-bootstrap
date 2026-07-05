import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import routing_hints as routing_hints_lib

from tests._helpers import class_requires_go

KIT = Path(__file__).resolve().parents[1]


def load_hook(path: Path):
    spec = importlib.util.spec_from_file_location("sop_hook_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@class_requires_go
class SopRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls.tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=cls.repo, check=True)
        subprocess.run([sys.executable, str(KIT / "install.py"), "--repo", str(cls.repo)], check=True, capture_output=True, text=True)
        cls.hook = load_hook(cls.repo / ".agent-loop/hooks/loop_hook.py")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def call(self, event, platform="claude"):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            rc = self.hook.handle(event, platform)
        self.assertEqual(rc, 0)
        raw = stream.getvalue()
        return json.loads(raw) if raw.strip() else {}

    def event(self, name, session, turn):
        return {"hook_event_name": name, "session_id": session, "turn_id": turn, "cwd": str(self.repo)}

    @staticmethod
    def command_route_body(candidate_frames, selected_frame, needs_user_turn, reason, confidence):
        return {
            "candidate_frames": candidate_frames,
            "selected_frame": selected_frame,
            "needs_user_turn": needs_user_turn,
            "reason": reason,
            "confidence": confidence,
        }

    def test_header_parser_excludes_uri(self):
        self.assertEqual(self.hook.sop_route("diag: inspect"), ("diag", "sop-diag", "inspect"))
        self.assertIsNone(self.hook.sop_route("https://example.com"))
        self.assertIsNone(self.hook.sop_route("Diag: inspect"))
        self.assertIsNone(self.hook.sop_route("brief: inspect"))
        self.assertEqual(self.hook.brief_route("brief: inspect"), "inspect")
        self.assertEqual(self.hook.brief_route("brief:"), "")
        self.assertIsNone(self.hook.sop_route("direct: inspect"))

    def test_diag_loads_skill_and_bypasses_gatekeeper(self):
        session, turn = "sop-diag-session", "sop-diag-turn"
        start = self.event("UserPromptSubmit", session, turn)
        start["prompt"] = "diag: investigate the failure"
        output = self.call(start, "claude")
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Required skill: sop-diag", context)
        self.assertIn("# SOP: Diagnostic investigation", context)
        self.assertNotIn("investigate the failure", context)
        state = json.loads((self.repo / f".agent-loop/runtime/sessions/{session}.json").read_text())
        self.assertEqual(state["routing_mode"], "SOP")
        self.assertTrue(state["sop"]["loaded"])
        self.assertFalse(state["sop"]["allow_mutations"])
        self.assertFalse((self.repo / f".agent-loop/runtime/turns/{turn}/gatekeeper.json").exists())

        read = self.event("PreToolUse", session, turn)
        read.update({"tool_name": "Bash", "tool_input": {"command": "git status --porcelain"}})
        self.assertEqual(self.call(read), {})

        write = self.event("PreToolUse", session, turn)
        write.update({"tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch"}})
        denied = self.call(write)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("read-only", denied["hookSpecificOutput"]["permissionDecisionReason"])

        stop = self.event("Stop", session, turn)
        stop.update({"background_tasks": []})
        self.assertEqual(self.call(stop), {})
        final = json.loads((self.repo / f".agent-loop/runtime/sessions/{session}.json").read_text())
        self.assertEqual(final["final_status"], "SOP_COMPLETE")

    def test_brief_prefix_enters_loop_and_skips_sop_resolution(self):
        session, turn = "brief-session", "brief-turn"
        start = self.event("UserPromptSubmit", session, turn)
        start["prompt"] = "brief: start the loop brief"
        output = self.call(start, "claude")
        self.assertIn("Loop Brief elicitation", output["hookSpecificOutput"]["additionalContext"])
        state = json.loads((self.repo / f".agent-loop/runtime/sessions/{session}.json").read_text(encoding="utf-8"))
        self.assertEqual(state["routing_mode"], "LOOP")
        self.assertEqual(state["entry_role"], "loop-brief-assistant")
        self.assertTrue((self.repo / f".agent-loop/runtime/turns/{turn}/brief-route.json").exists())
        self.assertFalse((self.repo / f".agent-loop/runtime/turns/{turn}/sop-route.json").exists())

    def test_install_header_loads_semantic_installer_sop(self):
        event = self.event("UserPromptSubmit", "install-sop", "install-turn")
        event["prompt"] = "install: merge this package into the repository"
        output = self.call(event, "codex")
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Required skill: sop-install", context)
        self.assertIn("# SOP: LLM-assisted installation", context)
        state = json.loads((self.repo / ".agent-loop/runtime/sessions/install-sop.json").read_text())
        self.assertEqual(state["routing_mode"], "SOP")
        self.assertTrue(state["sop"]["allow_mutations"])

    def test_route_loads_command_route_skill_and_selected_frame(self):
        session, turn = "route-session", "route-turn"
        start = self.event("UserPromptSubmit", session, turn)
        start["prompt"] = "route: help me decide the right planning frame"
        output = self.call(start, "claude")
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Required skill: command-route", context)
        self.assertIn("Routing mode: COMMAND_ROUTE", context)
        self.assertIn("candidate_shortlist:", context)
        self.assertIn("Choose this when you need a phased delivery plan that includes decisions, verification, and the next handoff.", context)
        state = json.loads((self.repo / f".agent-loop/runtime/sessions/{session}.json").read_text())
        self.assertEqual(state["routing_mode"], "COMMAND_ROUTE")
        self.assertTrue(state["command_route"]["loaded"])

        report = self.event("Stop", session, turn)
        report.update({
            "background_tasks": [],
            "last_assistant_message": json.dumps(self.command_route_body(
                [
                    {"frame": "frame-plandev", "confidence": 0.8, "reason": "multi-step delivery work"},
                    {"frame": "frame-first-principles", "confidence": 0.4, "reason": "needs decomposition"},
                ],
                "frame-plandev",
                False,
                "planning work is the best fit",
                0.8,
            )),
        })
        routed = self.call(report, "claude")
        routed_context = routed["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Required skill: frame-plandev", routed_context)
        self.assertIn("Routing mode: FRAME", routed_context)
        final_state = json.loads((self.repo / f".agent-loop/runtime/sessions/{session}.json").read_text())
        self.assertEqual(final_state["routing_mode"], "FRAME")
        self.assertTrue(final_state["frame"]["loaded"])
        self.assertEqual(final_state["frame"]["required_skill"], "frame-plandev")
        self.assertEqual(final_state["command_route"]["selected_frame"], "frame-plandev")
        self.assertTrue(final_state["command_route"]["frame_loaded"])

    def test_route_needs_user_turn_records_fallback(self):
        session, turn = "route-needs-input", "route-needs-turn"
        start = self.event("UserPromptSubmit", session, turn)
        start["prompt"] = "route: choose between several possible planning frames"
        output = self.call(start, "claude")
        self.assertIn("Required skill: command-route", output["hookSpecificOutput"]["additionalContext"])

        report = self.event("Stop", session, turn)
        report.update({
            "background_tasks": [],
            "last_assistant_message": json.dumps(self.command_route_body(
                [
                    {"frame": "frame-plandev", "confidence": 0.9, "reason": "delivery planning"},
                    {"frame": "frame-first-principles", "confidence": 0.9, "reason": "decomposition needed"},
                ],
                None,
                True,
                "the request is ambiguous",
                0.9,
            )),
        })
        result = self.call(report, "claude")
        self.assertEqual(result["stopReason"], "Command routing requires additional user input.")
        self.assertIn("frame-plandev", result["systemMessage"])
        self.assertIn("frame-first-principles", result["systemMessage"])
        self.assertIn("the request is ambiguous", result["systemMessage"])
        state = json.loads((self.repo / f".agent-loop/runtime/sessions/{session}.json").read_text())
        self.assertEqual(state["final_status"], "COMMAND_ROUTE_COMPLETE")
        self.assertTrue(state["command_route"]["needs_user_turn"])
        self.assertIsNone(state["command_route"]["selected_frame"])

    def test_list_loads_mode_index_sop(self):
        event = self.event("UserPromptSubmit", "list-sop", "list-turn")
        event["prompt"] = "list: show the current mode families"
        output = self.call(event, "claude")
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Required skill: sop-list", context)
        self.assertIn("# SOP: Mode index", context)
        self.assertIn("direct:", context)
        self.assertIn("frame-<name>", context)
        state = json.loads((self.repo / ".agent-loop/runtime/sessions/list-sop.json").read_text())
        self.assertEqual(state["routing_mode"], "SOP")
        self.assertEqual(state["sop"]["required_skill"], "sop-list")
        self.assertFalse(state["sop"]["allow_mutations"])



    def test_learning_audit_sop_requires_trusted_auditor_report(self):
        session, turn = "learning-audit-session", "learning-audit-turn"
        event = self.event("UserPromptSubmit", session, turn)
        event["prompt"] = "learning-audit: inspect the last 50 turns"
        output = self.call(event, "claude")
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Required skill: sop-learning-audit", context)

        start = self.event("SubagentStart", session, turn)
        start.update({"agent_type": "learning-auditor", "agent_id": "audit-1"})
        self.assertEqual(self.call(start), {})

        stop = self.event("Stop", session, turn)
        stop.update({"background_tasks": []})
        self.assertEqual(self.call(stop)["decision"], "block")

        report = self.event("SubagentStop", session, turn)
        report.update({
            "agent_type": "learning-auditor",
            "agent_id": "audit-1",
            "last_assistant_message": json.dumps({
                "role": "learning-auditor",
                "verdict": "UNKNOWN",
                "window": {"observed_turns": 0},
                "evidence_quality": ["insufficient data"],
                "learning_metrics_assessment": [],
                "recurrence_findings": [],
                "reuse_findings": [],
                "knowledge_debt_findings": [],
                "adaptation_findings": [],
                "memory_findings": [],
                "systemic_patterns": [],
                "recommended_policy_changes": [],
                "human_review_required": False,
            }),
        })
        self.assertEqual(self.call(report), {})
        self.assertEqual(self.call(stop), {})

    def test_missing_sop_blocks_prompt(self):
        event = self.event("UserPromptSubmit", "missing-sop", "missing-turn")
        event["prompt"] = "unknown: inspect this"
        output = self.call(event, "codex")
        self.assertEqual(output["decision"], "block")
        self.assertIn("sop-unknown", output["reason"])

    def test_normal_prompt_still_enters_gatekeeper(self):
        event = self.event("UserPromptSubmit", "normal-loop", "normal-turn")
        event["prompt"] = "investigate this"
        output = self.call(event, "codex")
        self.assertIn("Gatekeeper", output["hookSpecificOutput"]["additionalContext"])
        state = json.loads((self.repo / ".agent-loop/runtime/sessions/normal-loop.json").read_text())
        self.assertEqual(state["routing_mode"], "LOOP")

    def test_platform_skill_layout(self):
        self.assertTrue((self.repo / ".agents/skills/sop-diag/SKILL.md").exists())
        self.assertTrue((self.repo / ".agents/skills/sop-list/SKILL.md").exists())
        self.assertTrue((self.repo / ".agents/skills/command-route/SKILL.md").exists())
        self.assertTrue((self.repo / ".agents/skills/frame-plandev/routing.md").exists())
        self.assertTrue((self.repo / ".agents/skills/frame-wall/routing.md").exists())
        self.assertTrue((self.repo / ".claude/skills/sop-diag/SKILL.md").exists())
        self.assertTrue((self.repo / ".claude/skills/sop-list/SKILL.md").exists())
        self.assertTrue((self.repo / ".claude/skills/command-route/SKILL.md").exists())
        self.assertTrue((self.repo / ".claude/skills/frame-plandev/routing.md").exists())
        self.assertTrue((self.repo / ".claude/skills/frame-wall/routing.md").exists())
        self.assertTrue((self.repo / ".agent-loop/sop-policy.json").exists())
        self.assertTrue((self.repo / ".agent-loop/docs/COMMAND_ROUTING.md").exists())
        self.assertTrue((self.repo / ".agent-loop/docs/SOP_ROUTING.md").exists())

    def test_routing_md_parser_reads_toml_block(self):
        doc = routing_hints_lib.parse_routing_hints_toml(
            """# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plandev"
priority = 50
summary = "Multi-step delivery work."

[[prefer]]
phrase = "multi-step delivery"
weight = 4
```
"""
        )
        self.assertEqual(doc.schema, "routing-hints/v1")
        self.assertEqual(doc.frame, "frame-plandev")
        self.assertEqual(doc.priority, 50)
        self.assertEqual(doc.summary, "Multi-step delivery work.")
        self.assertEqual(doc.sections["prefer"][0].phrase, "multi-step delivery")

    def test_routing_hints_lint_passes(self):
        proc = subprocess.run(
            [sys.executable, str(KIT / "utils/routing_hints_lint.py"), "--root", str(self.repo)],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("OK: all routing hint files passed lint", proc.stdout)

    def test_routing_hints_lint_flags_asymmetric_avoid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frame-plandev").mkdir(parents=True)
            (root / "frame-plantask").mkdir(parents=True)
            (root / "frame-plandev/routing.md").write_text(
                """# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plandev"
priority = 90
summary = "phased planning"

[[prefer]]
phrase = "phased delivery plan"
aliases = ["段取り"]
weight = 4

[[avoid]]
phrase = "dependency DAG design"
aliases = ["依存関係"]
weight = -4

[[signals]]
phrase = "段取り"
weight = 1
```
""",
                encoding="utf-8",
            )
            (root / "frame-plantask/routing.md").write_text(
                """# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plantask"
priority = 80
summary = "task graph"

[[prefer]]
phrase = "dependency DAG design"
aliases = ["依存関係"]
weight = 4

[[avoid]]
phrase = "brief compression"
aliases = ["引き継ぎ"]
weight = -4

[[signals]]
phrase = "依存関係"
weight = 1
```
""",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(KIT / "utils/routing_hints_lint.py"), "--root", str(root)],
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("must avoid one of", proc.stdout)

    def test_routing_hints_lint_flags_missing_japanese_term(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frame-plandev").mkdir(parents=True)
            (root / "frame-plandev/routing.md").write_text(
                """# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plandev"
priority = 90
summary = "phased planning"

[[prefer]]
phrase = "phased delivery plan"
aliases = ["delivery"]
weight = 4

[[signals]]
phrase = "scope"
weight = 1
```
""",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(KIT / "utils/routing_hints_lint.py"), "--root", str(root)],
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("must include at least one Japanese term", proc.stdout)

    def test_routing_hints_lint_warns_on_duplicate_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frame-plandev").mkdir(parents=True)
            (root / "frame-plantask").mkdir(parents=True)
            (root / "frame-plandev/routing.md").write_text(
                """# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plandev"
priority = 90
summary = "phased planning"

[[prefer]]
phrase = "phased delivery plan"
aliases = ["段取り"]
weight = 4

[[avoid]]
phrase = "dependency DAG design"
aliases = ["依存関係"]
weight = -4

[[signals]]
phrase = "段取り"
weight = 1
```
""",
                encoding="utf-8",
            )
            (root / "frame-plantask/routing.md").write_text(
                """# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plantask"
priority = 90
summary = "task graph"

[[prefer]]
phrase = "dependency DAG design"
aliases = ["依存関係"]
weight = 4

[[avoid]]
phrase = "phased delivery plan"
aliases = ["フェーズ"]
weight = -4

[[signals]]
phrase = "依存関係"
weight = 1
```
""",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(KIT / "utils/routing_hints_lint.py"), "--root", str(root)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("WARNING:", proc.stdout)


if __name__ == "__main__":
    unittest.main()
