import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


class InstalledRepoSelfSufficiencyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("go"), "Go toolchain is required for the installed-repo smoke test")
    def test_install_builds_okfctl_and_wrapper_paths_work(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

            install = subprocess.run(
                [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(install.returncode, 0, install.stderr)

            binary = repo / ".agent-loop/bin/okfctl.bin"
            wrapper = repo / ".agent-loop/bin/okfctl"
            self.assertTrue(binary.is_file())
            self.assertTrue(os.access(binary, os.X_OK))

            version = subprocess.run(
                [str(wrapper), "version"],
                cwd=repo,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("0.3.0", version.stdout)

            report_path = repo / "no-changes-report.json"
            report_path.write_text(
                json.dumps({
                    "role": "memory-curator",
                    "status": "NO_CHANGES",
                    "processed_proposal_ids": [],
                    "operations": [],
                    "skipped_proposals": [],
                    "conflicts": [],
                    "validation_expectations": {"profile": "agent-loop-llmwiki-v1"},
                }, indent=2) + "\n",
                encoding="utf-8",
            )
            apply_report = subprocess.run(
                [str(wrapper), "apply-report", "--root", "llmwiki", "--report", str(report_path)],
                cwd=repo,
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(apply_report.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["status"], "NO_CHANGES")

    def test_install_fails_closed_without_go(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

            with tempfile.TemporaryDirectory() as empty_path:
                env = os.environ.copy()
                env["PATH"] = empty_path
                install = subprocess.run(
                    [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
                    text=True,
                    capture_output=True,
                    env=env,
                )
            self.assertNotEqual(install.returncode, 0)
            self.assertIn("Go 1.21+", install.stderr + install.stdout)
            self.assertIn("install.py", install.stderr + install.stdout)


if __name__ == "__main__":
    unittest.main()
