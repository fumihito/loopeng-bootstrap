from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._helpers import class_requires_go, normalize_repo_permissions


KIT = Path(__file__).resolve().parents[1]


@class_requires_go
class InstalledRepoSelfSufficiencyTests(unittest.TestCase):
    def test_installed_repo_can_self_update(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            subprocess.run(["git", "clone", "-q", "--no-local", str(KIT), str(repo)], check=True)

            subprocess.run(
                [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertTrue((repo / "install.py").is_file())
            normalize_repo_permissions(repo)

            proc = subprocess.run(
                [sys.executable, "install.py", "--repo", ".", "--self", "--update"],
                cwd=repo,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertEqual(proc.returncode, 0)
            self.assertTrue((repo / "install.py").is_file())
