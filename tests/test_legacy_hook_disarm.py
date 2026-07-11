from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
TARGET_EVENTS = {
    "UserPromptSubmit",
    "PreToolUse",
    "Stop",
    "StopFailure",
    "SubagentStart",
    "SubagentStop",
}


def _has_legacy_hook(payload: object) -> bool:
    if isinstance(payload, dict):
        return any(_has_legacy_hook(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_has_legacy_hook(item) for item in payload)
    if isinstance(payload, str):
        return "loop_hook.py" in payload
    return False


def _target_events(payload: dict[str, object]) -> list[object]:
    hooks = payload.get("hooks", {})
    if not isinstance(hooks, dict):
        return []
    return [hooks[event] for event in TARGET_EVENTS if event in hooks]


class LegacyHookDisarmTests(unittest.TestCase):
    def _install_routing_profile(self, repo: Path) -> None:
        subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo), "--profile", "routing"],
            text=True,
            capture_output=True,
            check=True,
        )

    def test_disarm_cli_preserves_other_hooks_and_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            self._install_routing_profile(repo)

            targets = [
                repo / ".claude" / "settings.json",
                repo / ".codex" / "hooks.json",
            ]
            for path in targets:
                path.chmod(0o644)
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload.setdefault("hooks", {}).setdefault("PreToolUse", []).append(
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo custom",
                            }
                        ]
                    }
                )
                path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, str(KIT / "utils" / "disarm_legacy_hooks.py"), "--repo", str(repo)],
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("Backups:", proc.stdout)
            self.assertIn("Removed", proc.stdout)

            for path in targets:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertFalse(any(_has_legacy_hook(event) for event in _target_events(payload)))
                hooks = payload["hooks"]["PreToolUse"]
                self.assertTrue(any(group["hooks"][0]["command"] == "echo custom" for group in hooks))
