from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

from tests._helpers import normalize_repo_permissions


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.py"


def load_install_module():
    spec = importlib.util.spec_from_file_location("install_self_apply_tests", INSTALL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def clone_repo_tree(destination: Path) -> None:
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".loop-engineering-backups"),
    )
    normalize_repo_permissions(destination)
    (destination / ".agent-loop/bin/okfctl.bin").unlink(missing_ok=True)


class SelfApplyInstallTests(unittest.TestCase):
    def test_self_flag_rejects_non_kit_repo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            proc = subprocess.run(
                ["python3", str(INSTALL), "--repo", str(repo), "--self"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("--self can only be used", proc.stderr + proc.stdout)

    def test_self_install_preserves_source_tree_and_installs_frozen_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            clone_repo_tree(repo)
            arch = repo / ".agent-loop/hooks/loop_hook.py"
            sentinel = "\nSELF-SOURCE-SHOULD-STAY\n"
            arch.write_text(arch.read_text(encoding="utf-8") + sentinel, encoding="utf-8")

            module = load_install_module()
            module.SRC = repo
            module.run_git = lambda *args, **kwargs: "a" * 40
            installer = module.Installer(repo, dry_run=False, conflict="error", profile="full")
            self.assertTrue(installer.maybe_self_mode())
            installer.install()

            self.assertIn("SELF-SOURCE-SHOULD-STAY", arch.read_text(encoding="utf-8"))
            manifest = json.loads((repo / ".agent-loop/runtime/install-manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["self_mode"])
            self.assertEqual(manifest["force_overwrite_tampered_reason"], None)

            frozen_md = (repo / ".claude/agents/gatekeeper.md").read_text(encoding="utf-8")
            self.assertIn("DO NOT EDIT", "\n".join(frozen_md.splitlines()[:10]))
            frozen_toml = (repo / ".codex/agents/gatekeeper.toml").read_text(encoding="utf-8")
            self.assertIn("DO NOT EDIT", frozen_toml.splitlines()[0])
            self.assertFalse(os.stat(repo / ".claude/agents/gatekeeper.md").st_mode & 0o222)
            self.assertFalse(os.stat(repo / ".codex/agents/gatekeeper.toml").st_mode & 0o222)
            self.assertTrue((repo / ".agent-loop/runtime/llmwiki-live").is_dir())
            self.assertEqual((repo / ".agent-loop/memory-policy.json").read_text(encoding="utf-8").count(".agent-loop/runtime/llmwiki-live"), 1)
            self.assertFalse((repo / ".agent-loop/bin/okfctl.bin").exists())

    def test_update_rejects_tampered_generated_file_and_force_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            clone_repo_tree(repo)
            module = load_install_module()
            module.SRC = repo
            module.run_git = lambda *args, **kwargs: "b" * 40
            installer = module.Installer(repo, dry_run=False, conflict="error", profile="full")
            installer.install()

            tampered = repo / ".codex/hooks.json"
            tampered.chmod(tampered.stat().st_mode | 0o200)
            tampered.write_text('{"tampered": true}\n', encoding="utf-8")

            updater = module.Installer(repo, dry_run=False, conflict="error", profile="full", self_mode=True, update_mode=True)
            with self.assertRaises(module.InstallerError) as ctx:
                updater.install()
            self.assertIn("--force-overwrite-tampered", str(ctx.exception))

            forced = module.Installer(
                repo,
                dry_run=False,
                conflict="error",
                profile="full",
                self_mode=True,
                update_mode=True,
                force_overwrite_tampered="needed to recover from local tampering",
            )
            forced.install()
            refreshed = (repo / ".codex/hooks.json").read_text(encoding="utf-8")
            self.assertNotIn('"tampered": true', refreshed)
            self.assertFalse(os.stat(repo / ".codex/hooks.json").st_mode & 0o222)
            manifest = json.loads((repo / ".agent-loop/runtime/install-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["force_overwrite_tampered_reason"],
                "needed to recover from local tampering",
            )

    def test_reserved_sop_brief_skill_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            clone_repo_tree(repo)
            for name in ("sop-brief", "sop-direct-edit"):
                reserved = repo / f"adapters/shared/skills/{name}"
                reserved.mkdir(parents=True)
                (reserved / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: Reserved.\nuser-invocable: true\n---\n\n# Reserved\n",
                    encoding="utf-8",
                )

            module = load_install_module()
            module.SRC = repo
            installer = module.Installer(repo, dry_run=False, conflict="error", profile="full")
            with self.assertRaises(module.InstallerError) as ctx:
                installer.should_install_skill("sop-brief")
            self.assertIn("reserved skill name is forbidden: sop-brief", str(ctx.exception))
            with self.assertRaises(module.InstallerError) as ctx:
                installer.should_install_skill("sop-direct-edit")
            self.assertIn("reserved skill name is forbidden: sop-direct-edit", str(ctx.exception))

    def test_update_preserves_user_changed_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            clone_repo_tree(repo)
            module = load_install_module()
            module.SRC = repo
            module.run_git = lambda *args, **kwargs: "c" * 40
            installer = module.Installer(repo, dry_run=False, conflict="error", profile="full")
            installer.install()

            policy = json.loads((repo / ".agent-loop/policy.json").read_text(encoding="utf-8"))
            policy["require_gatekeeper_before_mutation"] = False
            policy_path = repo / ".agent-loop/policy.json"
            policy_path.chmod(policy_path.stat().st_mode | 0o200)
            policy_path.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            updater = module.Installer(repo, dry_run=False, conflict="error", profile="full", self_mode=True, update_mode=True)
            updater.install()
            refreshed = json.loads(policy_path.read_text(encoding="utf-8"))
            self.assertFalse(refreshed["require_gatekeeper_before_mutation"])

    def test_self_update_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            clone_repo_tree(repo)
            module = load_install_module()
            module.SRC = repo
            module.run_git = lambda *args, **kwargs: "d" * 40
            installer = module.Installer(repo, dry_run=False, conflict="error", profile="full")
            installer.install()

            updater = module.Installer(repo, dry_run=False, conflict="error", profile="full", self_mode=True, update_mode=True)
            updater.install()
            second = module.Installer(repo, dry_run=False, conflict="error", profile="full", self_mode=True, update_mode=True)
            second.install()
            manifest = json.loads((repo / ".agent-loop/runtime/install-manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["update_mode"])


if __name__ == "__main__":
    unittest.main()
