from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
AL = '.' + 'agent-loop'


class InstallMigrationTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> Path:
        repo = root / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        (repo / AL / 'hooks').mkdir(parents=True)
        (repo / AL / 'lib').mkdir()
        (repo / AL / 'state' / 'turn-old').mkdir(parents=True)
        (repo / AL / 'state' / 'turn-old' / 'state.json').write_text('{}\n', encoding='utf-8')
        (repo / AL / 'unknown.txt').write_text('keep\n', encoding='utf-8')
        (repo / AL / 'hooks' / 'loop_hook.py').write_text('# old\n', encoding='utf-8')
        (repo / AL / 'policy.json').write_text('{}\n', encoding='utf-8')
        for platform, filename in [('claude', 'settings.json'), ('codex', 'hooks.json')]:
            path = repo / ('.' + platform) / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'hooks': {'Stop': [{'hooks': [{'command': 'loop_hook.py'}]}]}}) + '\n', encoding='utf-8')
        for root_name in ('skills', ('.' + 'claude') + '/skills', ('.' + 'agents') + '/skills'):
            skill = repo / root_name / 'gatekeeper'
            skill.mkdir(parents=True, exist_ok=True)
            (skill / 'SKILL.md').write_text('# old skill\n', encoding='utf-8')
        wiki = repo / 'llmwiki'
        (wiki / 'concepts').mkdir(parents=True)
        (wiki / 'loop-brief-patterns').mkdir()
        (wiki / 'loop-brief-patterns' / 'old.md').write_text('old\n', encoding='utf-8')
        (wiki / 'concepts' / 'valid.md').write_text('---\ntype: Concept\ntitle: Valid\ndescription: valid\ntags: [x]\ntimestamp: 2026-01-01\nstatus: accepted\nsensitivity: internal\nauthority: user\nconfidence: high\n---\n\nValid.\n', encoding='utf-8')
        (wiki / 'concepts' / 'invalid.md').write_text('not an OKF document\n', encoding='utf-8')
        return repo

    def run_install(self, repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(KIT / 'install.py'), '--repo', str(repo), '--profile', 'full', '--update', *extra], text=True, capture_output=True, check=False)

    def test_fixture_converges_and_second_run_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self.make_fixture(Path(td))
            first = self.run_install(repo)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertFalse((repo / AL / 'hooks' / 'loop_hook.py').exists())
            self.assertTrue((repo / 'loopeng' / 'cli.py').is_file())
            retired = sorted((repo / '.loop-engineering-backups').glob('*/v0.1-retired'))
            self.assertTrue(retired)
            self.assertTrue((retired[0] / AL / 'hooks' / 'loop_hook.py').is_file())
            self.assertTrue((repo / 'llmwiki' / 'concepts' / 'invalid.md').is_file())
            report = sorted((repo / AL / 'state' / 'reports').glob('migration-*.md'))[-1]
            body = report.read_text(encoding='utf-8')
            self.assertIn('invalid.md:', body)
            self.assertIn('unknown.txt', body)
            second = self.run_install(repo)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            reports = sorted((repo / AL / 'state' / 'reports').glob('migration-*.md'))
            self.assertGreaterEqual(len(reports), 2)
            self.assertIn('`no-op`', reports[-1].read_text(encoding='utf-8'))

    def test_dry_run_does_not_change_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self.make_fixture(Path(td))
            before = sorted((str(path.relative_to(repo)), path.read_bytes()) for path in repo.rglob('*') if path.is_file())
            proc = self.run_install(repo, '--dry-run')
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            after = sorted((str(path.relative_to(repo)), path.read_bytes()) for path in repo.rglob('*') if path.is_file())
            self.assertEqual(before, after)
            self.assertFalse((repo / '.loop-engineering-backups').exists())


if __name__ == '__main__':
    unittest.main()
