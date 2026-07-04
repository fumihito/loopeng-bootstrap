import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from utils.routing_hints_lint import CLUSTERS

KIT = Path(__file__).resolve().parents[1]


def load_hook(path: Path):
    spec = importlib.util.spec_from_file_location("routing_profile_hook", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RoutingProfileSelfSufficiencyTests(unittest.TestCase):
    def call(self, hook, event, platform="claude"):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            rc = hook.handle(event, platform)
        self.assertEqual(rc, 0)
        raw = stream.getvalue()
        return json.loads(raw) if raw.strip() else {}

    def event(self, repo: Path, name: str, session: str, turn: str) -> dict[str, str]:
        return {"hook_event_name": name, "session_id": session, "turn_id": turn, "cwd": str(repo)}

    def test_routing_profile_installs_without_go_and_keeps_routing_behaviour(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

            env = os.environ.copy()
            env["PATH"] = ""
            install = subprocess.run(
                [sys.executable, str(KIT / "install.py"), "--repo", str(repo), "--profile", "routing"],
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(install.returncode, 0, install.stderr + install.stdout)
            self.assertIn("Routing profile selected", install.stdout)
            self.assertFalse((repo / ".agent-loop/bin/okfctl.bin").exists())
            self.assertFalse((repo / ".agent-loop/systemd/agent-loop-scheduler.service").exists())
            self.assertFalse((repo / "llmwiki/index.md").exists())
            self.assertFalse((repo / "skills/gatekeeper/SKILL.md").exists())
            self.assertFalse((repo / ".codex/agents/gatekeeper.toml").exists())
            self.assertTrue((repo / ".agent-loop/policy.json").is_file())
            policy = json.loads((repo / ".agent-loop/policy.json").read_text(encoding="utf-8"))
            self.assertFalse(policy["loop_mode_enabled"])

            hook = load_hook(repo / ".agent-loop/hooks/loop_hook.py")

            passthrough = self.call(hook, {**self.event(repo, "UserPromptSubmit", "pass-session", "pass-turn"), "prompt": "hello"})
            self.assertEqual(passthrough, {})

            route = self.call(hook, {**self.event(repo, "UserPromptSubmit", "route-session", "route-turn"), "prompt": "route: help me decide the right planning frame"})
            self.assertIn("Required skill: command-route", route["hookSpecificOutput"]["additionalContext"])
            state = json.loads((repo / ".agent-loop/runtime/sessions/route-session.json").read_text(encoding="utf-8"))
            self.assertEqual(state["routing_mode"], "COMMAND_ROUTE")

            denied = self.call(hook, {**self.event(repo, "PreToolUse", "deny-session", "deny-turn"), "tool_name": "Bash", "tool_input": {"command": "rm -rf /"}})
            self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("Categorically destructive", denied["hookSpecificOutput"]["permissionDecisionReason"])

            blocked = self.call(hook, {
                **self.event(repo, "SubagentStop", "loop-session", "loop-turn"),
                "agent_type": "gatekeeper",
                "agent_id": "gatekeeper-1",
                "last_assistant_message": json.dumps({"role": "gatekeeper", "verdict": "READY"}),
            })
            self.assertEqual(blocked["decision"], "block")
            self.assertIn("loop_mode_enabled=false", blocked["reason"])

            frame_count = sum(len(frames) for frames in CLUSTERS.values())
            routing_files = sorted(repo.glob("skills/frame-*/routing.md"))
            self.assertEqual(len(routing_files), frame_count)
            for path in routing_files:
                self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
