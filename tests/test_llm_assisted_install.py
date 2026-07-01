import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


class LLMAssistedInstallTests(unittest.TestCase):
    def new_repo(self):
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name) / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
        return temp, repo

    def test_agent_plan_preserves_repository_and_contains_no_file_contents(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        legacy = 'LEGACY_PRIVATE_TOKEN_DO_NOT_COPY'
        (repo / '.codex').write_text(legacy, encoding='utf-8')
        plan = Path(temp.name) / 'plan'
        proc = subprocess.run(
            [
                sys.executable, str(KIT / 'install.py'), '--repo', str(repo),
                '--conflict', 'agent', '--agent-plan-dir', str(plan),
            ],
            text=True, capture_output=True,
        )
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertTrue((repo / '.codex').is_file())
        self.assertEqual((repo / '.codex').read_text(encoding='utf-8'), legacy)
        self.assertFalse((repo / '.agent-loop').exists())
        for name in ['INSTALL_AGENT.md', 'merge-plan.json', 'source-inventory.json', 'PROMPT.txt', 'INSTALL_MERGE_REPORT.md']:
            self.assertTrue((plan / name).is_file(), name)
        combined = ''.join(path.read_text(encoding='utf-8') for path in plan.iterdir() if path.is_file())
        self.assertNotIn(legacy, combined)
        data = json.loads((plan / 'merge-plan.json').read_text(encoding='utf-8'))
        self.assertTrue(any(item['relative_path'] == '.codex' for item in data['structural_conflicts']))
        conflict = next(item for item in data['structural_conflicts'] if item['relative_path'] == '.codex')
        self.assertIn('sha256', conflict['inventory'])
        self.assertFalse(data['security']['contents_embedded_in_plan'])

    def test_validate_only_succeeds_after_normal_install(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        install = subprocess.run(
            [sys.executable, str(KIT / 'install.py'), '--repo', str(repo)],
            text=True, capture_output=True,
        )
        self.assertEqual(install.returncode, 0, install.stderr)
        validate = subprocess.run(
            [sys.executable, str(KIT / 'install.py'), '--repo', str(repo), '--validate-only'],
            text=True, capture_output=True,
        )
        self.assertEqual(validate.returncode, 0, validate.stderr)
        self.assertIn('validation succeeded', validate.stdout.lower())

    def test_validate_only_detects_missing_component(self):
        temp, repo = self.new_repo()
        self.addCleanup(temp.cleanup)
        subprocess.run([sys.executable, str(KIT / 'install.py'), '--repo', str(repo)], check=True)
        (repo / '.agents/skills/sop-install/SKILL.md').unlink()
        validate = subprocess.run(
            [sys.executable, str(KIT / 'install.py'), '--repo', str(repo), '--validate-only'],
            text=True, capture_output=True,
        )
        self.assertEqual(validate.returncode, 4)
        self.assertIn('sop-install', validate.stderr)

    def test_install_sop_is_mutation_enabled(self):
        policy = json.loads((KIT / '.agent-loop/sop-policy.json').read_text(encoding='utf-8'))
        self.assertTrue(policy['skills']['sop-install']['allow_mutations'])
        self.assertTrue((KIT / 'adapters/shared/skills/sop-install/SKILL.md').is_file())
        self.assertTrue((KIT / 'adapters/shared/skills/sop-install/SKILL.md').is_file())


if __name__ == '__main__':
    unittest.main()
