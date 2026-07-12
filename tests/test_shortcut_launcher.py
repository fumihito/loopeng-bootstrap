from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]


class ShortcutLauncherTests(unittest.TestCase):
    def run_cli(self, command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, cwd=cwd, text=True, capture_output=True, env={**os.environ, "PYTHONPATH": ""})

    def test_launcher_matches_module_and_works_from_subdirectory(self) -> None:
        cases = [
            ["status"],
            ["okf", "validate", "llmwiki"],
            ["not-a-command"],
        ]
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run([sys.executable, str(KIT / "install.py"), "--repo", str(repo), "--profile", "full"], check=True, capture_output=True)
            for args in cases:
                launcher = self.run_cli([str(repo / "loopeng.py"), *args], repo)
                module = self.run_cli([sys.executable, "-m", "loopeng", *args], repo)
                self.assertEqual(launcher.returncode, module.returncode, args)
                self.assertEqual(launcher.stdout, module.stdout, args)
                self.assertEqual(launcher.stderr, module.stderr, args)

            nested = repo / "docs" / "nested"
            nested.mkdir(parents=True)
            launcher = self.run_cli(["../../loopeng.py", "status"], nested)
            module = self.run_cli([sys.executable, "-m", "loopeng", "status"], repo)
            self.assertEqual(launcher.returncode, module.returncode)
            self.assertEqual(launcher.stdout, module.stdout)
            self.assertEqual(launcher.stderr, module.stderr)

    def test_shadowing_resolves_package(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-c", "import loopeng; print(loopeng.__file__); print(hasattr(loopeng, '__path__'))"],
            cwd=KIT,
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONPATH": str(KIT)},
            check=True,
        )
        self.assertIn(str(KIT / "loopeng" / "__init__.py"), proc.stdout)
        self.assertIn("True", proc.stdout)

    def test_full_only_launcher_and_dispatcher(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            full = root / "full"
            routing = root / "routing"
            for repo, profile in ((full, "full"), (routing, "routing")):
                subprocess.run(["git", "init", "-q", str(repo)], check=True)
                subprocess.run([sys.executable, str(KIT / "install.py"), "--repo", str(repo), "--profile", profile], check=True, capture_output=True)
            self.assertTrue((full / "loopeng.py").is_file())
            self.assertTrue(os.access(full / "loopeng.py", os.X_OK))
            self.assertFalse((routing / "loopeng.py").exists())

            command_dir = root / "bin"
            installed = subprocess.run([sys.executable, str(KIT / "install.py"), "--install-command", str(command_dir)], text=True, capture_output=True, check=True)
            self.assertIn("Installed loopeng dispatcher", installed.stdout)
            dispatcher = command_dir / "loopeng"
            self.assertTrue(os.access(dispatcher, os.X_OK))
            nested = full / "docs" / "nested"
            nested.mkdir(parents=True)
            dispatched = self.run_cli([str(dispatcher), "status"], nested)
            direct = self.run_cli([str(full / "loopeng.py"), "status"], full)
            self.assertEqual(dispatched.returncode, direct.returncode)
            self.assertEqual(dispatched.stdout, direct.stdout)
            self.assertEqual(dispatched.stderr, direct.stderr)

            outside = self.run_cli([str(dispatcher), "status"], root)
            self.assertEqual(outside.returncode, 2)
            self.assertIn("no managed repository found", outside.stderr)

