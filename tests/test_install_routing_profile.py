from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from loopeng._paths import agent_root


KIT = Path(__file__).resolve().parents[1]


class InstallRoutingProfileTests(unittest.TestCase):
    def test_routing_profile_installs_only_frame_skills(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

            proc = subprocess.run(
                [sys.executable, str(KIT / "install.py"), "--repo", str(repo), "--profile", "routing"],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("Routing profile selected", proc.stdout)
            skill_root = repo / "skills"
            names = sorted(path.name for path in skill_root.iterdir() if path.is_dir())
            self.assertTrue(names)
            self.assertTrue(all(name.startswith("frame-") for name in names))
            self.assertFalse((repo / agent_root("bin", "okfctl.bin")).exists())

