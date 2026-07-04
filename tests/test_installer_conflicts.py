import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._helpers import class_requires_go

KIT = Path(__file__).resolve().parents[1]


@class_requires_go
class InstallerConflictTests(unittest.TestCase):
    def new_repo(self):
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        return temp, repo

    def test_codex_file_conflict_fails_before_changes(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        (repo / ".codex").write_text("legacy codex config\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("expected: directory", proc.stderr)
        self.assertIn("--conflict backup", proc.stderr)
        self.assertEqual((repo / ".codex").read_text(encoding="utf-8"), "legacy codex config\n")
        self.assertFalse((repo / ".agent-loop").exists())

    def test_backup_mode_relocates_codex_file_and_installs(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        (repo / ".codex").write_text("legacy codex config\n", encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(KIT / "install.py"),
                "--repo",
                str(repo),
                "--conflict",
                "backup",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((repo / ".codex").is_dir())
        self.assertTrue((repo / ".codex/hooks.json").is_file())
        backups = list((repo / ".loop-engineering-backups").glob("*/.codex"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "legacy codex config\n")
        manifest = json.loads((repo / ".agent-loop/runtime/install-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["conflict_policy"], "backup")
        self.assertTrue(any(a["action"] == "relocate-conflict" for a in manifest["actions"]))

    def test_existing_user_hooks_are_preserved(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        (repo / ".codex").mkdir()
        existing = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo user-hook"}]}
                ]
            }
        }
        (repo / ".codex/hooks.json").write_text(json.dumps(existing), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        merged = json.loads((repo / ".codex/hooks.json").read_text(encoding="utf-8"))
        serialized = json.dumps(merged)
        self.assertIn("echo user-hook", serialized)
        self.assertIn(".agent-loop/hooks/loop_hook.py", serialized)

    def test_dry_run_reports_conflict_without_modifying(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        (repo / ".claude").write_text("legacy", encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(KIT / "install.py"),
                "--repo",
                str(repo),
                "--dry-run",
                "--conflict",
                "backup",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("relocate structural conflict", proc.stdout)
        self.assertTrue((repo / ".claude").is_file())
        self.assertFalse((repo / ".agent-loop").exists())


@class_requires_go
class SharedCodexClaudeLayoutTests(unittest.TestCase):
    def new_repo(self):
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        return temp, repo

    def test_shared_internal_skill_symlinks_and_legacy_codex_toml_migrate(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        (repo / "skills").mkdir()
        (repo / ".agents").mkdir()
        (repo / ".claude").mkdir()
        (repo / ".agents/skills").symlink_to("../skills", target_is_directory=True)
        (repo / ".claude/skills").symlink_to("../skills", target_is_directory=True)
        legacy = 'model = "gpt-5.5-codex"\n[features]\nweb_search = true\n'
        (repo / ".codex").write_text(legacy, encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((repo / ".agents/skills").is_symlink())
        self.assertTrue((repo / ".claude/skills").is_symlink())
        self.assertEqual(__import__("os").readlink(repo / ".agents/skills"), "../skills/")
        self.assertEqual(__import__("os").readlink(repo / ".claude/skills"), "../skills/")
        self.assertEqual(
            (repo / ".agents/skills/gatekeeper/SKILL.md").resolve(),
            (repo / ".claude/skills/gatekeeper/SKILL.md").resolve(),
        )
        shared = (repo / "skills/gatekeeper/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("platform custom subagent", shared)
        self.assertNotIn("context: fork", shared)
        self.assertTrue((repo / ".codex").is_dir())
        self.assertEqual((repo / ".codex/config.toml").read_text(encoding="utf-8"), legacy)
        backups = list((repo / ".loop-engineering-backups").glob("*/.codex"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), legacy)
        manifest = json.loads((repo / ".agent-loop/runtime/install-manifest.json").read_text(encoding="utf-8"))
        actions = [item["action"] for item in manifest["actions"]]
        self.assertIn("migrate-legacy-codex-config", actions)
        self.assertIn("use-canonical-skill-root", actions)

        validate = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo), "--validate-only"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(validate.returncode, 0, validate.stderr)

        second = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue((repo / ".agents/skills").is_symlink())
        self.assertTrue((repo / ".claude/skills").is_symlink())
        self.assertEqual((repo / ".codex/config.toml").read_text(encoding="utf-8"), legacy)

    def test_broken_internal_shared_skill_symlinks_create_target(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        (repo / ".agents").mkdir()
        (repo / ".claude").mkdir()
        (repo / ".agents/skills").symlink_to("../skills", target_is_directory=True)
        (repo / ".claude/skills").symlink_to("../skills", target_is_directory=True)
        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((repo / "skills").is_dir())
        self.assertTrue((repo / "skills/sop-diag/SKILL.md").is_file())


    def test_recognized_layout_dry_run_is_non_mutating(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        (repo / ".agents").mkdir()
        (repo / ".claude").mkdir()
        (repo / ".agents/skills").symlink_to("../skills", target_is_directory=True)
        (repo / ".claude/skills").symlink_to("../skills", target_is_directory=True)
        legacy = 'model = "gpt-5.5-codex"\n'
        (repo / ".codex").write_text(legacy, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo), "--dry-run"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("migrate legacy Codex TOML", proc.stdout)
        self.assertIn("use canonical shared skills root", proc.stdout)
        self.assertTrue((repo / ".codex").is_file())
        self.assertFalse((repo / "skills").exists())
        self.assertFalse((repo / ".agent-loop").exists())


    def test_fresh_install_always_creates_one_real_skill_root(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True, capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((repo / "skills").is_dir())
        self.assertFalse((repo / "skills").is_symlink())
        self.assertEqual(__import__("os").readlink(repo / ".agents/skills"), "../skills/")
        self.assertEqual(__import__("os").readlink(repo / ".claude/skills"), "../skills/")
        self.assertTrue(__import__("os").path.samefile(
            repo / "skills/gatekeeper/SKILL.md",
            repo / ".agents/skills/gatekeeper/SKILL.md",
        ))
        self.assertTrue(__import__("os").path.samefile(
            repo / "skills/gatekeeper/SKILL.md",
            repo / ".claude/skills/gatekeeper/SKILL.md",
        ))

    def test_separate_physical_skill_roots_are_consolidated(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        (repo / ".agents/skills/custom-codex").mkdir(parents=True)
        (repo / ".agents/skills/custom-codex/SKILL.md").write_text(
            "---\nname: custom-codex\n---\nCodex custom.\n", encoding="utf-8"
        )
        (repo / ".claude/skills/custom-claude").mkdir(parents=True)
        (repo / ".claude/skills/custom-claude/SKILL.md").write_text(
            "---\nname: custom-claude\n---\nClaude custom.\n", encoding="utf-8"
        )
        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True, capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((repo / "skills/custom-codex/SKILL.md").is_file())
        self.assertTrue((repo / "skills/custom-claude/SKILL.md").is_file())
        self.assertEqual(__import__("os").readlink(repo / ".agents/skills"), "../skills/")
        self.assertEqual(__import__("os").readlink(repo / ".claude/skills"), "../skills/")
        backups = list((repo / ".loop-engineering-backups").glob("*/.agents/skills/custom-codex/SKILL.md"))
        self.assertEqual(len(backups), 1)
        backups = list((repo / ".loop-engineering-backups").glob("*/.claude/skills/custom-claude/SKILL.md"))
        self.assertEqual(len(backups), 1)



    def test_canonical_skills_symlink_is_materialized_without_backup_path_escape(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        (repo / "legacy-skills/gatekeeper").mkdir(parents=True)
        (repo / "legacy-skills/gatekeeper/SKILL.md").write_text(
            "---\nname: gatekeeper\n---\nlegacy shared variant\n", encoding="utf-8"
        )
        (repo / "skills").symlink_to("legacy-skills", target_is_directory=True)
        (repo / ".agents").mkdir()
        (repo / ".claude").mkdir()
        (repo / ".agents/skills").symlink_to("../skills/", target_is_directory=True)
        (repo / ".claude/skills").symlink_to("../skills/", target_is_directory=True)

        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True, capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((repo / "skills").is_dir())
        self.assertFalse((repo / "skills").is_symlink())
        metadata = list((repo / ".loop-engineering-backups").glob("*/.symlinks/skills.json"))
        self.assertEqual(len(metadata), 1)
        payload = json.loads(metadata[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["target"], "legacy-skills")
        expected = (KIT / "adapters/shared/skills/gatekeeper/SKILL.md").read_text(encoding="utf-8")
        self.assertEqual((repo / "skills/gatekeeper/SKILL.md").read_text(encoding="utf-8"), expected)
        self.assertIn("legacy shared variant", (repo / "legacy-skills/gatekeeper/SKILL.md").read_text(encoding="utf-8"))

    def test_legacy_platform_variants_of_managed_skill_are_replaced_by_shared_file(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        codex = repo / ".agents/skills/gatekeeper/SKILL.md"
        claude = repo / ".claude/skills/gatekeeper/SKILL.md"
        codex.parent.mkdir(parents=True)
        claude.parent.mkdir(parents=True)
        codex.write_text("---\nname: gatekeeper\n---\nlegacy codex variant\n", encoding="utf-8")
        claude.write_text("---\nname: gatekeeper\n---\nlegacy claude variant\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True, capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        expected = (KIT / "adapters/shared/skills/gatekeeper/SKILL.md").read_text(encoding="utf-8")
        self.assertEqual((repo / "skills/gatekeeper/SKILL.md").read_text(encoding="utf-8"), expected)
        codex_backups = list((repo / ".loop-engineering-backups").glob("*/.agents/skills/gatekeeper/SKILL.md"))
        claude_backups = list((repo / ".loop-engineering-backups").glob("*/.claude/skills/gatekeeper/SKILL.md"))
        self.assertEqual(len(codex_backups), 1)
        self.assertEqual(len(claude_backups), 1)
        self.assertIn("legacy codex variant", codex_backups[0].read_text(encoding="utf-8"))
        self.assertIn("legacy claude variant", claude_backups[0].read_text(encoding="utf-8"))

    def test_package_contains_only_one_skill_source_tree(self):
        self.assertTrue((KIT / "adapters/shared/skills").is_dir())
        self.assertFalse((KIT / "adapters/codex/.agents/skills").exists())
        self.assertFalse((KIT / "adapters/claude/.claude/skills").exists())

    def test_unknown_conflicting_skill_files_are_rejected_without_changes(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        for parent, body in [(".agents", "A"), (".claude", "B")]:
            path = repo / parent / "skills/custom/SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"---\nname: custom\n---\n{body}\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True, capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cannot deterministically merge", proc.stderr)
        self.assertTrue((repo / ".agents/skills").is_dir())
        self.assertTrue((repo / ".claude/skills").is_dir())
        self.assertFalse((repo / "skills").exists())
        self.assertFalse((repo / ".agent-loop").exists())

    def test_external_skill_symlink_is_rejected(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(outside, ignore_errors=True))
        (repo / ".agents").mkdir()
        (repo / ".agents/skills").symlink_to(outside, target_is_directory=True)
        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("resolves outside the repository", proc.stderr)
        self.assertFalse((repo / ".agent-loop").exists())

    def test_invalid_legacy_codex_file_remains_a_conflict(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        (repo / ".codex").write_text("not valid = [toml\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--repo", str(repo)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cannot migrate the legacy .codex file deterministically", proc.stderr)
        self.assertTrue((repo / ".codex").is_file())
        self.assertFalse((repo / ".agent-loop").exists())

if __name__ == "__main__":
    unittest.main()
