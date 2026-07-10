from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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

    def test_routing_profile_does_not_redistribute_legacy_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

            self._install_routing_profile(repo)

            legacy_parts = {"v0.1", "loop-control"}
            legacy_paths = [
                path.relative_to(repo)
                for path in repo.rglob("*")
                if any(part in legacy_parts for part in path.relative_to(repo).parts)
            ]
            self.assertFalse(legacy_paths, legacy_paths)
