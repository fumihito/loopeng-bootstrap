from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from utils.phase1_gate import LEGACY_ARTIFACTS


KIT = Path(__file__).resolve().parents[1]


class RoutingProfileSelfSufficiencyTests(unittest.TestCase):
    def _install_routing_profile(self, repo: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo), "--profile", "routing"],
            text=True,
            capture_output=True,
            check=True,
        )

    def test_routing_profile_installs_only_frame_skills(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

            proc = self._install_routing_profile(repo)

            self.assertIn("Routing profile selected", proc.stdout)
            skill_root = repo / "skills"
            names = sorted(path.name for path in skill_root.iterdir() if path.is_dir())
            self.assertTrue(names)
            self.assertTrue(all(name.startswith("frame-") for name in names))
            self.assertFalse((repo / "bin" / "okfctl.bin").exists())

    def test_routing_profile_update_removes_legacy_hook_registrations(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

            self._install_routing_profile(repo)
            proc = subprocess.run(
                [sys.executable, str(KIT / "install.py"), "--repo", str(repo), "--profile", "routing", "--update"],
                text=True,
                capture_output=True,
                check=True,
            )

            for rel, events in [
                ((".claude", "settings.json"), ("UserPromptSubmit", "PreToolUse", "Stop", "StopFailure", "SubagentStart", "SubagentStop")),
                ((".codex", "hooks.json"), ("UserPromptSubmit", "PreToolUse", "Stop", "StopFailure", "SubagentStart", "SubagentStop")),
            ]:
                payload = json.loads(Path(repo, *rel).read_text(encoding="utf-8"))
                hooks = payload.get("hooks", {})
                self.assertTrue(isinstance(hooks, dict))
                for event in events:
                    for group in hooks.get(event, []):
                        self.assertNotIn("loop_hook.py", json.dumps(group))

    def test_routing_profile_does_not_redistribute_legacy_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

            self._install_routing_profile(repo)

            legacy_paths = [rel for rel in LEGACY_ARTIFACTS if (repo / rel).exists()]
            self.assertFalse(legacy_paths, legacy_paths)
