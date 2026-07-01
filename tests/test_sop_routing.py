import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


def load_hook(path: Path):
    spec = importlib.util.spec_from_file_location("sop_hook_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def test_header_parser_excludes_uri(self):
        self.assertEqual(self.hook.sop_route("diag: inspect"), ("diag", "sop-diag", "inspect"))
        self.assertIsNone(self.hook.sop_route("https://example.com"))
        self.assertIsNone(self.hook.sop_route("Diag: inspect"))
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
        self.assertTrue((self.repo / ".claude/skills/sop-diag/SKILL.md").exists())
        self.assertTrue((self.repo / ".claude/skills/sop-list/SKILL.md").exists())
        self.assertTrue((self.repo / ".agent-loop/sop-policy.json").exists())
        self.assertTrue((self.repo / ".agent-loop/docs/SOP_ROUTING.md").exists())


if __name__ == "__main__":
    unittest.main()
