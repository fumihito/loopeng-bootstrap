#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import hashlib
import re
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import routing_hints as routing_hints_lib

SRC = Path(__file__).resolve().parent
BEGIN = '<!-- LOOP-ENGINEERING:BEGIN -->'
END = '<!-- LOOP-ENGINEERING:END -->'
MANAGED_HOOK_MARKER = '.agent-loop/hooks/loop_hook.py'
GO_MINIMUM_VERSION = '1.21'
RUNTIME_MANIFEST = [
    '.agent-loop/hooks/loop_hook.py',
    '.agent-loop/policy.json',
    '.agent-loop/scheduler-policy.json',
    '.agent-loop/learning-policy.json',
    '.agent-loop/memory-policy.json',
    '.agent-loop/brief-pattern-policy.json',
    '.agent-loop/sop-policy.json',
    '.agent-loop/direct-policy.json',
    '.agent-loop/bin/learning_health.py',
    '.agent-loop/bin/next_turn_scheduler.py',
    '.agent-loop/bin/next_turn_scheduler_daemon.py',
    '.agent-loop/bin/okfctl',
    '.agent-loop/bin/build-okfctl.sh',
    '.agent-loop/cmd/okfctl/main.go',
    '.agent-loop/lib/learning_observer.py',
    '.agent-loop/otel.json',
    '.agent-loop/otel-collector.yaml',
    'routing_hints.py',
]


def stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')


@dataclass(frozen=True)
class Conflict:
    path: Path
    expected: str
    actual: str
    reason: str


@dataclass(frozen=True)
class LayoutMigration:
    source: Path
    destination: Path
    kind: str
    reason: str


class InstallerError(RuntimeError):
    pass


class Installer:
    def __init__(self, repo: Path, *, dry_run: bool, conflict: str) -> None:
        self.repo = repo
        self.dry_run = dry_run
        self.conflict = conflict
        self.run_stamp = stamp()
        self.backup_root = repo / '.loop-engineering-backups' / self.run_stamp
        self.actions: list[dict[str, str]] = []

    def describe(self, path: Path) -> str:
        if path.is_symlink():
            try:
                return f'symlink -> {os.readlink(path)}'
            except OSError:
                return 'symlink'
        if path.is_dir():
            return 'directory'
        if path.is_file():
            return 'file'
        if path.exists():
            return 'special filesystem node'
        return 'absent'

    def rel(self, path: Path) -> Path:
        try:
            return path.resolve(strict=False).relative_to(self.repo.resolve())
        except ValueError as exc:
            raise InstallerError(f'Path escapes repository: {path}') from exc

    def is_inside_repository(self, path: Path) -> bool:
        try:
            resolved = path.resolve(strict=False)
            root = self.repo.resolve()
        except (OSError, RuntimeError):
            return False
        return resolved == root or root in resolved.parents

    @property
    def canonical_skill_root(self) -> Path:
        return self.repo / 'skills'

    @property
    def platform_skill_links(self) -> tuple[Path, Path]:
        return (self.repo / '.agents/skills', self.repo / '.claude/skills')

    @staticmethod
    def canonical_skill_link_target() -> str:
        # Keep the trailing slash so `ls -al` shows the intended directory target.
        return '../skills/'

    def managed_skill_files(self) -> set[Path]:
        source_root = SRC / 'adapters/shared/skills'
        return {
            path.relative_to(source_root)
            for path in source_root.rglob('*')
            if path.is_file()
        }

    def command_skill_names(self) -> list[str]:
        source_root = SRC / 'adapters/shared/skills'
        names: list[str] = []
        for path in sorted(source_root.glob('command-*/SKILL.md')):
            if not path.is_file() or path.is_symlink():
                continue
            names.append(path.parent.name)
        return names

    def routing_hint_paths(self) -> list[Path]:
        return [
            path
            for path in sorted(self.repo.rglob('routing.md'))
            if path.is_file() and '.git' not in path.relative_to(self.repo).parts
        ]

    def inspect_skill_tree(self, root: Path) -> list[Conflict]:
        conflicts: list[Conflict] = []
        if not root.exists():
            return conflicts
        if not root.is_dir():
            return [Conflict(
                root, 'directory', self.describe(root),
                'skill tree source is not a directory',
            )]
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                conflicts.append(Conflict(
                    path, 'regular file or directory', self.describe(path),
                    'nested symlinks inside the canonical skill tree are rejected',
                ))
        return conflicts

    def skill_source_roots(self) -> tuple[list[Path], list[Conflict]]:
        roots: list[Path] = []
        conflicts: list[Conflict] = []
        canonical = self.canonical_skill_root

        if canonical.is_symlink():
            try:
                target = canonical.resolve(strict=False)
            except (OSError, RuntimeError) as exc:
                conflicts.append(Conflict(
                    canonical, 'real directory', self.describe(canonical),
                    f'cannot resolve canonical skills symlink safely: {exc}',
                ))
            else:
                if not self.is_inside_repository(target):
                    conflicts.append(Conflict(
                        canonical, 'repository-local real directory', self.describe(canonical),
                        'canonical skills symlink resolves outside the repository',
                    ))
                elif target.exists() and not target.is_dir():
                    conflicts.append(Conflict(
                        canonical, 'symlink to a directory', self.describe(canonical),
                        f'canonical skills target is not a directory: {target}',
                    ))
                else:
                    roots.append(target)
        elif canonical.exists():
            if canonical.is_dir():
                roots.append(canonical)
            else:
                conflicts.append(Conflict(
                    canonical, 'real directory', self.describe(canonical),
                    'canonical skills root is not a directory',
                ))

        for link in self.platform_skill_links:
            parent = link.parent
            if parent.is_symlink():
                conflicts.append(Conflict(
                    parent, 'real directory', self.describe(parent),
                    'platform configuration root may not be a symlink',
                ))
                continue
            if parent.exists() and not parent.is_dir():
                conflicts.append(Conflict(
                    parent, 'directory', self.describe(parent),
                    'platform configuration root is not a directory',
                ))
                continue
            if link.is_symlink():
                try:
                    target = link.resolve(strict=False)
                except (OSError, RuntimeError) as exc:
                    conflicts.append(Conflict(
                        link, f'symlink to {canonical}', self.describe(link),
                        f'cannot resolve platform skills symlink safely: {exc}',
                    ))
                    continue
                if not self.is_inside_repository(target):
                    conflicts.append(Conflict(
                        link, f'symlink to {canonical}', self.describe(link),
                        'platform skills symlink resolves outside the repository',
                    ))
                    continue
                if target.exists() and not target.is_dir():
                    conflicts.append(Conflict(
                        link, f'symlink to {canonical}', self.describe(link),
                        f'platform skills target is not a directory: {target}',
                    ))
                    continue
                roots.append(target)
            elif link.exists():
                if link.is_dir():
                    roots.append(link)
                else:
                    conflicts.append(Conflict(
                        link, f'symlink to {canonical}', self.describe(link),
                        'platform skills path is neither a directory nor a symlink',
                    ))

        unique: list[Path] = []
        seen: set[str] = set()
        for item in roots:
            key = str(item.resolve(strict=False))
            if key not in seen:
                unique.append(item)
                seen.add(key)
        return unique, conflicts

    def skill_collision_conflicts(self, roots: list[Path]) -> list[Conflict]:
        conflicts: list[Conflict] = []
        managed = self.managed_skill_files()
        seen_files: dict[Path, tuple[str, Path]] = {}
        seen_dirs: set[Path] = set()
        for source_root in roots:
            if not source_root.exists():
                continue
            conflicts.extend(self.inspect_skill_tree(source_root))
            if conflicts:
                continue
            for path in sorted(source_root.rglob('*')):
                relative = path.relative_to(source_root)
                if path.is_dir():
                    if relative in seen_files:
                        conflicts.append(Conflict(
                            path,
                            'mergeable skill tree', 'file/directory collision',
                            f'{path} is a directory but another source provides a file',
                        ))
                    seen_dirs.add(relative)
                    continue
                if not path.is_file():
                    continue
                if relative in seen_dirs:
                    conflicts.append(Conflict(
                        path,
                        'mergeable skill tree', 'directory/file collision',
                        f'{path} is a file but another source provides a directory',
                    ))
                    continue
                digest = self.sha256_file(path)
                prior = seen_files.get(relative)
                if prior is None:
                    seen_files[relative] = (digest, path)
                    continue
                prior_digest, prior_path = prior
                if digest != prior_digest and relative not in managed:
                    conflicts.append(Conflict(
                        path,
                        'identical content or a package-managed shared skill',
                        'different files from multiple legacy skill roots',
                        f'cannot deterministically merge {prior_path} and {path}',
                    ))
        return conflicts

    def skill_install_layout(self) -> tuple[list[tuple[Path, Path, str]], list[Conflict]]:
        roots, conflicts = self.skill_source_roots()
        conflicts.extend(self.skill_collision_conflicts(roots))
        if conflicts:
            return [], conflicts
        return [
            (SRC / 'adapters/shared/skills', self.canonical_skill_root, 'canonical-shared')
        ], []

    def skill_layout_migrations(self) -> tuple[list[LayoutMigration], list[Conflict]]:
        migrations: list[LayoutMigration] = []
        roots, conflicts = self.skill_source_roots()
        conflicts.extend(self.skill_collision_conflicts(roots))
        if conflicts:
            return [], conflicts

        canonical = self.canonical_skill_root
        if canonical.is_symlink():
            migrations.append(LayoutMigration(
                source=canonical,
                destination=canonical,
                kind='materialize-canonical-skills',
                reason='the canonical {ROOT}/skills path must be a real directory',
            ))

        canonical_resolved = canonical.resolve(strict=False)
        expected_target = self.canonical_skill_link_target()
        for link in self.platform_skill_links:
            if link.is_symlink():
                try:
                    target = link.resolve(strict=False)
                    raw_target = os.readlink(link)
                except (OSError, RuntimeError) as exc:
                    conflicts.append(Conflict(
                        link, f'symlink to {canonical}', self.describe(link),
                        f'cannot inspect platform skills symlink: {exc}',
                    ))
                    continue
                if target == canonical_resolved and raw_target == expected_target:
                    continue
                migrations.append(LayoutMigration(
                    source=link,
                    destination=canonical,
                    kind='repoint-platform-skills',
                    reason='platform skills must use the exact relative symlink ../skills/',
                ))
            elif link.is_dir():
                migrations.append(LayoutMigration(
                    source=link,
                    destination=canonical,
                    kind='consolidate-platform-skills',
                    reason='platform-specific skill directories are consolidated into {ROOT}/skills',
                ))
            elif not link.exists():
                migrations.append(LayoutMigration(
                    source=link,
                    destination=canonical,
                    kind='create-platform-skill-link',
                    reason='both clients must resolve skills through {ROOT}/skills',
                ))
        return migrations, conflicts

    def layout_migrations(self) -> tuple[list[LayoutMigration], list[Conflict]]:
        migrations: list[LayoutMigration] = []
        conflicts: list[Conflict] = []

        skill_migrations, skill_conflicts = self.skill_layout_migrations()
        migrations.extend(skill_migrations)
        conflicts.extend(skill_conflicts)

        codex = self.repo / '.codex'
        if codex.is_symlink():
            conflicts.append(Conflict(
                codex, 'directory', self.describe(codex),
                'the .codex root may not be a symlink; migrate it explicitly',
            ))
        elif codex.is_file():
            try:
                body = codex.read_text(encoding='utf-8')
                value = tomllib.loads(body)
                if not isinstance(value, dict):
                    raise ValueError('TOML root is not a table')
            except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, ValueError) as exc:
                conflicts.append(Conflict(
                    codex, 'directory or valid legacy Codex TOML file', 'file',
                    f'cannot migrate the legacy .codex file deterministically: {type(exc).__name__}: {exc}',
                ))
            else:
                migrations.append(LayoutMigration(
                    source=codex,
                    destination=codex / 'config.toml',
                    kind='legacy-codex-toml',
                    reason='Codex project configuration is supported at .codex/config.toml',
                ))
        return migrations, conflicts

    def destination_paths(self) -> list[Path]:
        paths: list[Path] = []
        paths.extend(self.repo / rel for rel in RUNTIME_MANIFEST)
        paths.append(self.repo / '.agent-loop/systemd/agent-loop-scheduler.service')
        paths.extend(self.repo / rel for rel in [
            '.agent-loop/docs/GATEKEEPER_PROTOCOL.md',
            '.agent-loop/docs/LOOP_BRIEF_ASSISTANT.md',
            '.agent-loop/docs/LOOP_BRIEF_PATTERN_MEMORY.md',
            '.agent-loop/docs/DIRECT_MODE.md',
            '.agent-loop/docs/COMMAND_ROUTING.md',
            '.agent-loop/docs/LOOP_INPUT_GUIDE.md',
            '.agent-loop/docs/HUMAN_SKILL_NAMESPACE.md',
            '.agent-loop/docs/SOP_ROUTING.md',
            '.agent-loop/docs/LLM_ASSISTED_INSTALL.md',
            '.agent-loop/docs/MERGE_RULES.md',
            '.agent-loop/docs/SHARED_LAYOUTS.md',
            '.agent-loop/docs/DESIGN_PHILOSOPHY.md',
            '.agent-loop/docs/ARCHITECTURE.md',
            '.agent-loop/docs/LEARNING_OBSERVABILITY.md',
            '.agent-loop/docs/OKF_LLMWIKI.md',
            '.agent-loop/templates/LOOP_BRIEF.md',
            '.agent-loop/templates/OKF_CONCEPT.md',
            '.agent-loop/templates/OKF_LOOP_BRIEF_PATTERN.md',
            '.agent-loop/templates/SOP_SKILL_TEMPLATE.md',
            '.agent-loop/templates/INSTALL_MERGE_REPORT.md',
            '.codex/hooks.json',
            '.claude/settings.json',
            'AGENTS.md',
            'CLAUDE.md',
            '.gitignore',
        ])
        for source in (SRC / "llmwiki").rglob("*"):
            if source.is_file():
                paths.append(self.repo / "llmwiki" / source.relative_to(SRC / "llmwiki"))
        skill_mappings, _ = self.skill_install_layout()
        mappings = [
            *skill_mappings,
            (SRC / 'adapters/codex/.codex/agents', self.repo / '.codex/agents', 'codex-agents'),
            (SRC / 'adapters/claude/.claude/agents', self.repo / '.claude/agents', 'claude-agents'),
        ]
        for source_base, target_base, _ in mappings:
            for source in source_base.rglob('*'):
                if source.is_file():
                    paths.append(target_base / source.relative_to(source_base))
        return paths

    def analyze_layout(self) -> tuple[list[Conflict], list[LayoutMigration]]:
        conflicts: dict[Path, Conflict] = {}
        skill_mappings, skill_conflicts = self.skill_install_layout()
        del skill_mappings
        for item in skill_conflicts:
            conflicts[item.path] = item
        migrations, migration_conflicts = self.layout_migrations()
        for item in migration_conflicts:
            conflicts[item.path] = item
        migratable_sources = {item.source for item in migrations}

        for destination in self.destination_paths():
            parent = destination.parent
            while parent != self.repo.parent and parent != self.repo:
                if parent in migratable_sources:
                    parent = parent.parent
                    continue
                if parent.is_symlink():
                    conflicts.setdefault(parent, Conflict(
                        parent, 'directory', self.describe(parent),
                        'symlinked installation parent is not an approved internal skills root',
                    ))
                    break
                if parent.exists() and not parent.is_dir():
                    conflicts.setdefault(parent, Conflict(
                        parent, 'directory', self.describe(parent),
                        'a parent required as a directory already exists as a non-directory node',
                    ))
                    break
                parent = parent.parent
            if destination.is_symlink():
                conflicts.setdefault(destination, Conflict(
                    destination, 'regular file', self.describe(destination),
                    'managed file destination is a symlink',
                ))
            elif destination.exists() and destination.is_dir() and destination.name not in {'.gitignore'}:
                conflicts.setdefault(destination, Conflict(
                    destination, 'regular file', 'directory',
                    'managed file destination already exists as a directory',
                ))
        backup_anchor = self.repo / '.loop-engineering-backups'
        if backup_anchor.exists() and not backup_anchor.is_dir():
            conflicts[backup_anchor] = Conflict(
                backup_anchor, 'directory', self.describe(backup_anchor),
                'backup root is not a directory',
            )
        return sorted(conflicts.values(), key=lambda item: str(item.path)), migrations

    def preflight(self) -> list[Conflict]:
        conflicts, _ = self.analyze_layout()
        return conflicts

    def print_conflicts(self, conflicts: Iterable[Conflict]) -> None:
        print('Installation cannot proceed because filesystem layout conflicts were found:', file=sys.stderr)
        for item in conflicts:
            print(f'  - {item.path}', file=sys.stderr)
            print(f'      expected: {item.expected}', file=sys.stderr)
            print(f'      actual:   {item.actual}', file=sys.stderr)
            print(f'      reason:   {item.reason}', file=sys.stderr)
        print('', file=sys.stderr)
        print('Inspect the paths before changing them. For semantic inspection and merge planning, run:', file=sys.stderr)
        print(f'  {sys.executable} {Path(__file__).resolve()} --repo {self.repo} --conflict agent', file=sys.stderr)
        print('Use --conflict backup only after deciding that plain relocation is correct.', file=sys.stderr)

    def backup_path(self, path: Path) -> Path:
        relative = path.relative_to(self.repo)
        return self.backup_root / relative

    def record(self, action: str, source: Path | None, destination: Path) -> None:
        self.actions.append({
            'action': action,
            'source': str(source) if source else '',
            'destination': str(destination),
        })

    def preserve_symlink_metadata(self, path: Path) -> Path:
        if not path.is_symlink():
            raise InstallerError(f'Expected a symlink to preserve: {path}')
        relative = path.relative_to(self.repo).as_posix().replace('/', '__')
        destination = self.backup_root / '.symlinks' / f'{relative}.json'
        target = os.readlink(path)
        if self.dry_run:
            print(f'[dry-run] preserve symlink metadata {path} -> {destination}')
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            raise InstallerError(f'Symlink metadata backup unexpectedly exists: {destination}')
        destination.write_text(
            json.dumps({'path': str(path.relative_to(self.repo)), 'target': target}, indent=2) + '\n',
            encoding='utf-8',
        )
        self.record('backup-symlink-metadata', path, destination)
        return destination

    def relocate_conflict(self, conflict: Conflict) -> None:
        source = conflict.path
        destination = self.backup_path(source)
        if source.is_symlink():
            metadata = self.preserve_symlink_metadata(source)
            if self.dry_run:
                print(f'[dry-run] remove conflicting symlink after metadata backup {source}')
                return
            source.unlink()
            self.record('relocate-symlink-conflict', source, metadata)
            return
        if self.dry_run:
            print(f'[dry-run] relocate structural conflict {source} -> {destination}')
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            raise InstallerError(f'Backup destination unexpectedly exists: {destination}')
        shutil.move(str(source), str(destination))
        self.record('relocate-conflict', source, destination)

    def merge_skill_tree(self, source_root: Path, target_root: Path) -> None:
        if not source_root.exists():
            return
        managed = self.managed_skill_files()
        if self.dry_run:
            print(f'[dry-run] merge legacy skill tree {source_root} -> {target_root}')
            return
        target_root.mkdir(parents=True, exist_ok=True)
        for source in sorted(source_root.rglob('*')):
            if source.is_symlink():
                raise InstallerError(f'Nested skill symlink was not migrated: {source}')
            relative = source.relative_to(source_root)
            destination = target_root / relative
            if source.is_dir():
                if destination.exists() and not destination.is_dir():
                    raise InstallerError(f'Skill merge file/directory collision: {destination}')
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if not source.is_file():
                continue
            if destination.exists():
                if not destination.is_file() or destination.is_symlink():
                    raise InstallerError(f'Skill merge destination is not a regular file: {destination}')
                if self.sha256_file(source) == self.sha256_file(destination):
                    continue
                if relative in managed:
                    # The current shared package version is installed after consolidation.
                    self.record('defer-managed-skill-replacement', source, destination)
                    continue
                raise InstallerError(f'Unknown skill content conflict: {source} -> {destination}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            self.record('merge-legacy-skill', source, destination)

    def create_canonical_skill_link(self, link: Path) -> None:
        target = self.canonical_skill_link_target()
        if self.dry_run:
            print(f'[dry-run] create symlink {link} -> {target}')
            return
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.exists() or link.is_symlink():
            raise InstallerError(f'Cannot create canonical skills symlink over existing node: {link}')
        os.symlink(target, link, target_is_directory=True)
        self.record('create-canonical-skill-link', None, link)

    def apply_layout_migration(self, migration: LayoutMigration) -> None:
        source = migration.source
        destination = migration.destination

        if migration.kind == 'legacy-codex-toml':
            backup = self.backup_path(source)
            if self.dry_run:
                print(f'[dry-run] migrate legacy Codex TOML {source} -> {destination}; backup -> {backup}')
                return
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists() or backup.is_symlink():
                raise InstallerError(f'Backup destination unexpectedly exists: {backup}')
            shutil.move(str(source), str(backup))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, destination)
            self.record('backup-layout-source', source, backup)
            self.record('migrate-legacy-codex-config', backup, destination)
            print(f'Migrated legacy Codex configuration: {source} -> {destination}')
            return

        if migration.kind == 'materialize-canonical-skills':
            try:
                old_target = source.resolve(strict=False)
            except (OSError, RuntimeError) as exc:
                raise InstallerError(f'Cannot resolve canonical skills symlink: {source}: {exc}') from exc
            metadata = self.preserve_symlink_metadata(source)
            if self.dry_run:
                print(f'[dry-run] materialize canonical skills {source}; merge {old_target} -> {destination}')
                return
            source.unlink()
            destination.mkdir(parents=True, exist_ok=True)
            self.merge_skill_tree(old_target, destination)
            self.record('materialize-canonical-skill-root', metadata, destination)
            return

        if migration.kind == 'repoint-platform-skills':
            try:
                old_tree = source.resolve(strict=False)
            except (OSError, RuntimeError) as exc:
                raise InstallerError(f'Cannot resolve platform skills link: {source}: {exc}') from exc
            metadata = self.preserve_symlink_metadata(source)
            if self.dry_run:
                print(f'[dry-run] merge {old_tree} into {destination}; repoint {source} -> {self.canonical_skill_link_target()}')
                return
            source.unlink()
            destination.mkdir(parents=True, exist_ok=True)
            self.merge_skill_tree(old_tree, destination)
            self.create_canonical_skill_link(source)
            self.record('repoint-platform-skill-root', metadata, destination)
            return

        if migration.kind == 'consolidate-platform-skills':
            backup = self.backup_path(source)
            if self.dry_run:
                print(f'[dry-run] consolidate {source} into {destination}; backup directory -> {backup}; relink -> {self.canonical_skill_link_target()}')
                return
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(backup))
            destination.mkdir(parents=True, exist_ok=True)
            self.merge_skill_tree(backup, destination)
            self.create_canonical_skill_link(source)
            self.record('consolidate-platform-skill-root', backup, destination)
            return

        if migration.kind == 'create-platform-skill-link':
            if self.dry_run:
                self.create_canonical_skill_link(source)
                return
            destination.mkdir(parents=True, exist_ok=True)
            self.create_canonical_skill_link(source)
            return

        raise InstallerError(f'Unknown layout migration: {migration.kind}')

    def ensure_parent(self, path: Path) -> None:
        parent = path.parent
        if self.dry_run:
            return
        parent.mkdir(parents=True, exist_ok=True)

    def backup_existing(self, path: Path) -> None:
        if not (path.exists() or path.is_symlink()):
            return
        if path.is_dir() or path.is_symlink():
            raise InstallerError(f'Cannot file-backup structural node: {path}')
        destination = self.backup_path(path)
        if self.dry_run:
            print(f'[dry-run] backup {path} -> {destination}')
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(path, destination)
            self.record('backup-file', path, destination)

    def atomic_write_text(self, path: Path, text: str) -> None:
        self.ensure_parent(path)
        if self.dry_run:
            print(f'[dry-run] write {path}')
            return
        fd, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=str(path.parent))
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            self.record('write', None, path)
        finally:
            temp_path.unlink(missing_ok=True)

    def copy_file(self, source: Path, destination: Path) -> None:
        if self.dry_run:
            print(f'[dry-run] copy {source.relative_to(SRC)} -> {destination}')
            return
        self.backup_existing(destination)
        self.ensure_parent(destination)
        shutil.copy2(source, destination)
        self.record('copy', source, destination)

    def copy_rendered_file(self, source: Path, destination: Path, *, replacements: dict[str, str]) -> None:
        if self.dry_run:
            print(f'[dry-run] render {source.relative_to(SRC)} -> {destination}')
            return
        self.backup_existing(destination)
        self.ensure_parent(destination)
        text = source.read_text(encoding='utf-8')
        for needle, replacement in replacements.items():
            text = text.replace(needle, replacement)
        self.atomic_write_text(destination, text)
        self.record('copy', source, destination)

    def copy_file_if_missing(self, source: Path, destination: Path) -> None:
        if destination.exists() or destination.is_symlink():
            if destination.is_file() and not destination.is_symlink():
                return
            raise InstallerError(f'Cannot preserve non-file LLMWiki destination: {destination}')
        if self.dry_run:
            print(f'[dry-run] create missing {source.relative_to(SRC)} -> {destination}')
            return
        self.ensure_parent(destination)
        shutil.copy2(source, destination)
        self.record('copy-missing', source, destination)

    def install_llmwiki_skeleton(self) -> None:
        source_root = SRC / 'llmwiki'
        target_root = self.repo / 'llmwiki'
        if target_root.is_symlink():
            raise InstallerError(f'LLMWiki root must not be a symlink: {target_root}')
        if target_root.exists() and not target_root.is_dir():
            raise InstallerError(f'LLMWiki root must be a directory: {target_root}')
        for source in sorted(source_root.rglob('*')):
            if source.is_file():
                self.copy_file_if_missing(source, target_root / source.relative_to(source_root))

    def merge_json(self, source: Path, destination: Path) -> None:
        incoming = json.loads(source.read_text(encoding='utf-8'))
        current: dict = {}
        if destination.exists():
            if not destination.is_file():
                raise InstallerError(f'JSON destination is not a regular file: {destination}')
            try:
                current = json.loads(destination.read_text(encoding='utf-8'))
            except json.JSONDecodeError as exc:
                raise InstallerError(
                    f'Existing JSON is invalid and was not modified: {destination}: {exc}'
                ) from exc
        if not isinstance(current, dict):
            raise InstallerError(f'Existing JSON root must be an object: {destination}')
        current.setdefault('hooks', {})
        if not isinstance(current['hooks'], dict):
            raise InstallerError(f'Existing hooks field must be an object: {destination}')

        # Replace only previous versions of this kit; preserve unrelated user hooks.
        for event, groups in list(current['hooks'].items()):
            if not isinstance(groups, list):
                raise InstallerError(f'Hook event {event!r} must contain a list: {destination}')
            current['hooks'][event] = [
                group for group in groups
                if MANAGED_HOOK_MARKER not in json.dumps(group, sort_keys=True)
            ]
        for event, groups in incoming.get('hooks', {}).items():
            current['hooks'].setdefault(event, [])
            seen = {json.dumps(item, sort_keys=True) for item in current['hooks'][event]}
            for group in groups:
                key = json.dumps(group, sort_keys=True)
                if key not in seen:
                    current['hooks'][event].append(group)
                    seen.add(key)

        if 'env' in incoming:
            current.setdefault('env', {})
            if not isinstance(current['env'], dict):
                raise InstallerError(f'Existing env field must be an object: {destination}')
            privacy_keys = {
                'OTEL_LOG_USER_PROMPTS', 'OTEL_LOG_TOOL_DETAILS',
                'OTEL_LOG_TOOL_CONTENT', 'OTEL_LOG_RAW_API_BODIES',
            }
            for key, value in incoming['env'].items():
                if key in privacy_keys:
                    current['env'][key] = value
                else:
                    current['env'].setdefault(key, value)

        if self.dry_run:
            print(f'[dry-run] merge {source.relative_to(SRC)} -> {destination}')
            return
        self.backup_existing(destination)
        self.atomic_write_text(destination, json.dumps(current, indent=2, ensure_ascii=False) + '\n')

    def patch_marked_file(self, path: Path, snippet: str) -> None:
        old = path.read_text(encoding='utf-8') if path.exists() else ''
        block = BEGIN + '\n' + snippet.rstrip() + '\n' + END
        if BEGIN in old and END in old:
            prefix = old.split(BEGIN, 1)[0].rstrip()
            suffix = old.split(END, 1)[1].lstrip()
            new = '\n\n'.join(part for part in [prefix, block, suffix] if part) + '\n'
        elif BEGIN in old or END in old:
            raise InstallerError(f'Only one loop-engineering marker exists; refusing ambiguous patch: {path}')
        else:
            new = old.rstrip() + ('\n\n' if old.strip() else '') + block + '\n'
        if self.dry_run:
            print(f'[dry-run] patch {path}')
            return
        self.backup_existing(path)
        self.atomic_write_text(path, new)

    def patch_gitignore(self) -> None:
        path = self.repo / '.gitignore'
        lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
        additions = [
            '.agent-loop/runtime/',
            '.agent-loop/bin/okfctl.bin',
            '.loop-engineering-backups/',
        ]
        missing = [line for line in additions if line not in lines]
        if not missing:
            return
        text = path.read_text(encoding='utf-8') if path.exists() else ''
        if text and not text.endswith('\n'):
            text += '\n'
        if text and not text.endswith('\n\n'):
            text += '\n'
        text += '# Loop Engineering runtime and installer backups\n'
        text += ''.join(f'{line}\n' for line in missing)
        if self.dry_run:
            print(f'[dry-run] patch {path}')
            return
        self.backup_existing(path)
        self.atomic_write_text(path, text)

    def ensure_go_toolchain(self) -> str:
        if shutil.which('go') is None:
            raise InstallerError(
                f'Go {GO_MINIMUM_VERSION}+ is required; install.py must fail closed rather than defer this to runtime.'
            )
        try:
            completed = subprocess.run(
                ['go', 'version'], cwd=self.repo, text=True, capture_output=True, check=False,
            )
        except OSError as exc:
            raise InstallerError(f'cannot execute Go toolchain: {type(exc).__name__}: {exc}') from exc
        output = (completed.stdout or completed.stderr or '').strip()
        if completed.returncode != 0:
            raise InstallerError(f'Go toolchain check failed: {output or "go version returned a non-zero exit status"}')
        match = re.search(r'go1\.(\d+)', output)
        if not match:
            raise InstallerError(f'Go toolchain version is unclear from `{output or "go version"}`; {GO_MINIMUM_VERSION}+ is required')
        if int(match.group(1)) < 21:
            raise InstallerError(f'{output} is too old; {GO_MINIMUM_VERSION}+ is required')
        return output

    def build_okfctl(self) -> None:
        source = self.repo / '.agent-loop/cmd/okfctl/main.go'
        binary = self.repo / '.agent-loop/bin/okfctl.bin'
        if not source.is_file():
            raise InstallerError(f'missing Go source for okfctl: {source}')
        self.ensure_go_toolchain()
        fd, tmp_name = tempfile.mkstemp(prefix='.okfctl.bin.', dir=str(binary.parent))
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            env = os.environ.copy()
            env['GOWORK'] = 'off'
            env['GOCACHE'] = env.get('GOCACHE', '/tmp/loopeng-gocache')
            Path(env['GOCACHE']).mkdir(parents=True, exist_ok=True)
            completed = subprocess.run(
                ['go', 'build', '-trimpath', '-ldflags', '-s -w', '-o', str(tmp), str(source)],
                cwd=self.repo, text=True, capture_output=True, env=env, check=False,
            )
            if completed.returncode != 0:
                stderr = completed.stderr.strip() or completed.stdout.strip() or 'go build failed'
                raise InstallerError(f'okfctl build failed: {stderr}')
            tmp.chmod(0o755)
            os.replace(tmp, binary)
        finally:
            tmp.unlink(missing_ok=True)

    def run_okfctl(self, *args: str) -> subprocess.CompletedProcess[str]:
        binary = self.repo / '.agent-loop/bin/okfctl'
        if not binary.is_file():
            raise InstallerError(f'missing okfctl wrapper: {binary}')
        try:
            return subprocess.run(
                [str(binary), *args], cwd=self.repo, text=True, capture_output=True, check=False,
            )
        except OSError as exc:
            raise InstallerError(f'cannot execute okfctl: {type(exc).__name__}: {exc}') from exc

    @staticmethod
    def sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    def inventory_entry(self, path: Path) -> dict[str, object]:
        entry: dict[str, object] = {
            'path': str(path),
            'relative_path': str(path.relative_to(self.repo)) if path == self.repo or self.repo in path.parents else None,
            'type': self.describe(path),
        }
        if path.is_symlink():
            entry['symlink_target'] = os.readlink(path)
        elif path.is_file():
            entry['size_bytes'] = path.stat().st_size
            entry['sha256'] = self.sha256_file(path)
        return entry

    def merge_strategy(self, destination: Path) -> str:
        rel = destination.relative_to(self.repo).as_posix()
        if rel in {'.codex/hooks.json', '.claude/settings.json'}:
            return 'structured-json-merge'
        if rel in {'AGENTS.md', 'CLAUDE.md'}:
            return 'managed-markdown-block-merge'
        if rel == '.gitignore':
            return 'set-union-lines'
        if '/skills/' in rel or '/agents/' in rel:
            return 'semantic-role-or-skill-merge'
        if rel.startswith('.agent-loop/'):
            return 'managed-core-replace-or-port-local-extension'
        return 'copy-after-backup'

    def generate_agent_plan(
        self, conflicts: list[Conflict], migrations: list[LayoutMigration],
        plan_dir: Path | None,
    ) -> Path:
        destination = (plan_dir or (
            self.repo.parent / f'.{self.repo.name}.loop-engineering-install-plan-{self.run_stamp}'
        )).expanduser().resolve()
        if destination == self.repo or self.repo in destination.parents:
            raise InstallerError('Agent plan directory must be outside the target repository.')
        if destination.exists():
            raise InstallerError(f'Agent plan directory already exists: {destination}')
        destination.mkdir(parents=True)

        existing = []
        for path in sorted(set(self.destination_paths()), key=str):
            if path.exists() or path.is_symlink():
                item = self.inventory_entry(path)
                item['merge_strategy'] = self.merge_strategy(path)
                existing.append(item)

        source_files = []
        for path in sorted(SRC.rglob('*')):
            if not path.is_file() or '.git' in path.parts or '__pycache__' in path.parts:
                continue
            source_files.append({
                'relative_path': path.relative_to(SRC).as_posix(),
                'size_bytes': path.stat().st_size,
                'sha256': self.sha256_file(path),
            })

        plan = {
            'schema_version': 1,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source_version': (SRC / 'VERSION').read_text(encoding='utf-8').strip(),
            'source_root': str(SRC),
            'repository_root': str(self.repo),
            'plan_directory': str(destination),
            'deterministic_layout_migrations': [
                {
                    'source': str(item.source),
                    'destination': str(item.destination),
                    'kind': item.kind,
                    'reason': item.reason,
                }
                for item in migrations
            ],
            'structural_conflicts': [
                {
                    'path': str(item.path),
                    'relative_path': str(item.path.relative_to(self.repo)),
                    'expected': item.expected,
                    'actual': item.actual,
                    'reason': item.reason,
                    'inventory': self.inventory_entry(item.path),
                }
                for item in conflicts
            ],
            'existing_managed_destinations': existing,
            'source_inventory_file': 'source-inventory.json',
            'merge_rules': str(SRC / 'docs/MERGE_RULES.md'),
            'instruction_file': str(destination / 'INSTALL_AGENT.md'),
            'report_template': str(SRC / 'templates/INSTALL_MERGE_REPORT.md'),
            'deterministic_install_command': f'{sys.executable} {SRC / "install.py"} --repo {self.repo}',
            'validation_command': f'{sys.executable} {SRC / "install.py"} --repo {self.repo} --validate-only',
            'security': {
                'contents_embedded_in_plan': False,
                'secret_values_must_not_be_logged': True,
                'external_symlinks_forbidden': True,
                'blind_overwrite_forbidden': True,
            },
        }
        (destination / 'merge-plan.json').write_text(
            json.dumps(plan, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
        )
        (destination / 'source-inventory.json').write_text(
            json.dumps(source_files, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
        )
        instructions = (SRC / 'INSTALL_AGENT.md').read_text(encoding='utf-8')
        header = (
            f'<!-- generated installation context -->\n'
            f'- source_root: `{SRC}`\n'
            f'- repository_root: `{self.repo}`\n'
            f'- plan_path: `{destination / "merge-plan.json"}`\n'
            f'- validation_command: `{plan["validation_command"]}`\n\n'
        )
        (destination / 'INSTALL_AGENT.md').write_text(header + instructions, encoding='utf-8')
        (destination / 'INSTALL_MERGE_REPORT.md').write_text(
            (SRC / 'templates/INSTALL_MERGE_REPORT.md').read_text(encoding='utf-8'),
            encoding='utf-8',
        )
        prompt = (
            'Act as the installation agent. Read and follow this file exactly:\n'
            f'{destination / "INSTALL_AGENT.md"}\n'
            'Perform a semantic merge into the target repository, preserve existing behavior, '
            'avoid exposing secrets, run the validation command, and complete INSTALL_MERGE_REPORT.md.\n'
        )
        (destination / 'PROMPT.txt').write_text(prompt, encoding='utf-8')
        return destination

    def validate_installation(self) -> list[str]:
        errors: list[str] = []
        frame_skills = [
            'frame-diag',
            'frame-plandev',
            'frame-plantask',
            'frame-first-principles',
            'frame-experiments',
            'frame-cynefin',
            'frame-smeac',
            'frame-proofread-ja',
            'frame-blind-spot',
            'frame-inertia',
            'frame-waiwad-grill',
            'frame-distributed-incident-analysis',
            'frame-critical-review',
            'frame-research-arch',
            'frame-research-tactics',
        ]

        canonical_skills = self.canonical_skill_root
        if canonical_skills.is_symlink() or not canonical_skills.is_dir():
            errors.append('canonical skills root must be a real directory: skills')
        expected_skill_target = self.canonical_skill_link_target()
        for rel in ['.agents/skills', '.claude/skills']:
            link = self.repo / rel
            if not link.is_symlink():
                errors.append(f'platform skills path must be a symlink: {rel}')
                continue
            try:
                raw_target = os.readlink(link)
                resolved = link.resolve(strict=False)
            except (OSError, RuntimeError) as exc:
                errors.append(f'cannot resolve skills symlink {rel}: {type(exc).__name__}: {exc}')
                continue
            if raw_target != expected_skill_target:
                errors.append(f'platform skills symlink is not normalized: {rel} -> {raw_target!r}; expected {expected_skill_target!r}')
            if resolved != canonical_skills.resolve(strict=False):
                errors.append(f'platform skills symlink does not resolve to skills/: {rel} -> {resolved}')
            elif not resolved.is_dir():
                errors.append(f'platform skills target is not a directory: {rel} -> {resolved}')

        codex_config = self.repo / '.codex/config.toml'
        if codex_config.is_file():
            try:
                value = tomllib.loads(codex_config.read_text(encoding='utf-8'))
                if not isinstance(value, dict):
                    errors.append('TOML root is not a table: .codex/config.toml')
            except Exception as exc:
                errors.append(f'invalid TOML .codex/config.toml: {type(exc).__name__}: {exc}')
        required_files = [
            *RUNTIME_MANIFEST,
            '.agent-loop/systemd/agent-loop-scheduler.service',
            '.agent-loop/docs/GATEKEEPER_PROTOCOL.md',
            '.agent-loop/docs/LOOP_BRIEF_ASSISTANT.md',
            '.agent-loop/docs/LOOP_BRIEF_PATTERN_MEMORY.md',
            '.agent-loop/docs/DIRECT_MODE.md',
            '.agent-loop/docs/COMMAND_ROUTING.md',
            '.agent-loop/docs/DESIGN_PHILOSOPHY.md',
            '.agent-loop/docs/ARCHITECTURE.md',
            '.agent-loop/docs/HUMAN_SKILL_NAMESPACE.md',
            '.agent-loop/docs/LEARNING_OBSERVABILITY.md',
            '.agent-loop/docs/OKF_LLMWIKI.md',
            '.agent-loop/templates/OKF_CONCEPT.md',
            '.agent-loop/templates/OKF_LOOP_BRIEF_PATTERN.md',
            'llmwiki/index.md',
            'llmwiki/loop-brief-patterns/index.md',
            'llmwiki/log.md',
            '.codex/hooks.json',
            '.claude/settings.json',
            'AGENTS.md',
            'CLAUDE.md',
        ]
        for rel in required_files:
            path = self.repo / rel
            if not path.is_file() or path.is_symlink():
                errors.append(f'missing or unsafe required file: {rel}')

        for rel in ['.codex/hooks.json', '.claude/settings.json', '.agent-loop/policy.json', '.agent-loop/scheduler-policy.json', '.agent-loop/learning-policy.json', '.agent-loop/memory-policy.json', '.agent-loop/brief-pattern-policy.json', '.agent-loop/sop-policy.json', '.agent-loop/direct-policy.json', '.agent-loop/otel.json']:
            path = self.repo / rel
            if path.is_file():
                try:
                    value = json.loads(path.read_text(encoding='utf-8'))
                    if not isinstance(value, dict):
                        errors.append(f'JSON root is not an object: {rel}')
                except Exception as exc:
                    errors.append(f'invalid JSON {rel}: {type(exc).__name__}: {exc}')

        for rel in ['.codex/hooks.json', '.claude/settings.json']:
            path = self.repo / rel
            if path.is_file() and MANAGED_HOOK_MARKER not in path.read_text(encoding='utf-8'):
                errors.append(f'managed hook command absent: {rel}')

        roles = ['gatekeeper', 'loop-brief-assistant', 'brief-pattern-curator', 'sensemaker', 'integrator', 'governor', 'state-steward', 'watchdog-recovery', 'meta-evaluator', 'learning-auditor', 'memory-curator']
        for role in roles:
            toml_path = self.repo / f'.codex/agents/{role}.toml'
            if toml_path.is_file():
                try:
                    value = tomllib.loads(toml_path.read_text(encoding='utf-8'))
                    if not isinstance(value, dict):
                        errors.append(f'TOML root is not a table: .codex/agents/{role}.toml')
                except Exception as exc:
                    errors.append(f'invalid TOML .codex/agents/{role}.toml: {type(exc).__name__}: {exc}')

        def skill_name(path: Path) -> str | None:
            try:
                body = path.read_text(encoding='utf-8')
            except OSError:
                return None
            if not body.startswith('---\n'):
                return None
            end = body.find('\n---\n', 4)
            if end < 0:
                return None
            for line in body[4:end].splitlines():
                if line.startswith('name:'):
                    return line.split(':', 1)[1].strip().strip('\"\'')
            return None

        for role in roles:
            canonical = self.repo / f'skills/{role}/SKILL.md'
            for rel in [
                f'skills/{role}/SKILL.md',
                f'.codex/agents/{role}.toml',
                f'.claude/agents/{role}.md',
            ]:
                path = self.repo / rel
                if not path.is_file() or path.is_symlink():
                    errors.append(f'missing or unsafe role component: {rel}')
                elif rel.endswith('/SKILL.md') and skill_name(path) != role:
                    errors.append(f'skill frontmatter name mismatch: {rel}')
            for rel in [f'.agents/skills/{role}/SKILL.md', f'.claude/skills/{role}/SKILL.md']:
                path = self.repo / rel
                if not path.is_file():
                    errors.append(f'missing platform-visible role skill: {rel}')
                else:
                    try:
                        if not os.path.samefile(path, canonical):
                            errors.append(f'platform role skill is not the canonical shared file: {rel}')
                    except OSError as exc:
                        errors.append(f'cannot compare platform role skill identity: {rel}: {exc}')
        for frame in frame_skills:
            canonical = self.repo / f'skills/{frame}/SKILL.md'
            if not canonical.is_file() or canonical.is_symlink():
                errors.append(f'missing or unsafe human frame skill: skills/{frame}/SKILL.md')
                continue
            if skill_name(canonical) != frame:
                errors.append(f'frame skill frontmatter name mismatch: skills/{frame}/SKILL.md')
            for rel in [f'.agents/skills/{frame}/SKILL.md', f'.claude/skills/{frame}/SKILL.md']:
                path = self.repo / rel
                if not path.is_file():
                    errors.append(f'missing platform-visible frame skill: {rel}')
                else:
                    try:
                        if not os.path.samefile(path, canonical):
                            errors.append(f'platform frame skill is not the canonical shared file: {rel}')
                    except OSError as exc:
                        errors.append(f'cannot compare platform frame skill identity: {rel}: {exc}')
        for skill in self.command_skill_names():
            canonical = self.repo / f'skills/{skill}/SKILL.md'
            if not canonical.is_file() or canonical.is_symlink():
                errors.append(f'missing or unsafe command route skill: skills/{skill}/SKILL.md')
                continue
            if skill_name(canonical) != skill:
                errors.append(f'command route skill frontmatter name mismatch: skills/{skill}/SKILL.md')
            for rel in [f'.agents/skills/{skill}/SKILL.md', f'.claude/skills/{skill}/SKILL.md']:
                path = self.repo / rel
                if not path.is_file():
                    errors.append(f'missing platform-visible command route skill: {rel}')
                else:
                    try:
                        if not os.path.samefile(path, canonical):
                            errors.append(f'platform command route skill is not the canonical shared file: {rel}')
                    except OSError as exc:
                        errors.append(f'cannot compare platform command route skill identity: {rel}: {exc}')
        for path in self.routing_hint_paths():
            try:
                document = routing_hints_lib.load_routing_hints(path)
                errors.extend(
                    f'routing hint invalid: {path.relative_to(self.repo)}: {message}'
                    for message in routing_hints_lib.validate_routing_hints_document(document, expected_frame=path.parent.name)
                )
            except Exception as exc:
                errors.append(f'routing hint invalid: {path.relative_to(self.repo)}: {type(exc).__name__}: {exc}')
        for skill in ['sop-diag', 'sop-list', 'sop-install', 'sop-learning-audit']:
            canonical = self.repo / f'skills/{skill}/SKILL.md'
            if not canonical.is_file() or canonical.is_symlink():
                errors.append(f'missing or unsafe canonical SOP skill: skills/{skill}/SKILL.md')
                continue
            if skill_name(canonical) != skill:
                errors.append(f'SOP skill frontmatter name mismatch: skills/{skill}/SKILL.md')
            for rel in [f'.agents/skills/{skill}/SKILL.md', f'.claude/skills/{skill}/SKILL.md']:
                path = self.repo / rel
                if not path.is_file():
                    errors.append(f'missing platform-visible SOP skill: {rel}')
                else:
                    try:
                        if not os.path.samefile(path, canonical):
                            errors.append(f'platform SOP skill is not the canonical shared file: {rel}')
                    except OSError as exc:
                        errors.append(f'cannot compare platform SOP skill identity: {rel}: {exc}')

        for rel in ['AGENTS.md', 'CLAUDE.md']:
            path = self.repo / rel
            if path.is_file():
                body = path.read_text(encoding='utf-8')
                if body.count(BEGIN) != 1 or body.count(END) != 1:
                    errors.append(f'invalid managed instruction markers: {rel}')

        okf_binary = self.repo / '.agent-loop/bin/okfctl.bin'
        if not okf_binary.exists():
            errors.append('missing built okfctl binary: .agent-loop/bin/okfctl.bin')
        elif not os.access(okf_binary, os.X_OK):
            errors.append('built okfctl binary is not executable: .agent-loop/bin/okfctl.bin')
        else:
            try:
                completed = subprocess.run(
                    [str(okf_binary), 'validate', '--root', 'llmwiki', '--json'],
                    cwd=self.repo, text=True, capture_output=True, timeout=30, check=False,
                )
                if completed.returncode != 0:
                    errors.append('OKF LLMWiki validation failed; run .agent-loop/bin/okfctl validate --root llmwiki for details')
            except (OSError, subprocess.TimeoutExpired) as exc:
                errors.append(f'cannot execute built OKF validator: {type(exc).__name__}: {exc}')

        return errors

    def write_install_manifest(self) -> None:
        if self.dry_run:
            return
        manifest = {
            'installed_at': datetime.now(timezone.utc).isoformat(),
            'source_version': (SRC / 'VERSION').read_text(encoding='utf-8').strip(),
            'conflict_policy': self.conflict,
            'backup_root': str(self.backup_root.relative_to(self.repo)) if self.backup_root.exists() else None,
            'actions': self.actions,
        }
        path = self.repo / '.agent-loop' / 'install-manifest.json'
        self.atomic_write_text(path, json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')

    def install(self, *, agent_plan_dir: Path | None = None) -> None:
        conflicts, migrations = self.analyze_layout()
        if self.conflict == 'agent':
            plan = self.generate_agent_plan(conflicts, migrations, agent_plan_dir)
            print(f'LLM-assisted installation plan created: {plan}')
            print(f'Read: {plan / "INSTALL_AGENT.md"}')
            raise SystemExit(3)
        if conflicts and self.conflict == 'error':
            self.print_conflicts(conflicts)
            raise SystemExit(2)
        if conflicts and self.conflict == 'backup':
            for item in conflicts:
                self.relocate_conflict(item)

        remaining, migrations = self.analyze_layout()
        if remaining and not self.dry_run:
            self.print_conflicts(remaining)
            raise SystemExit(2)
        if not self.dry_run:
            self.ensure_go_toolchain()
        for migration in migrations:
            self.apply_layout_migration(migration)
        if not self.dry_run:
            after_migration, _ = self.analyze_layout()
            if after_migration:
                self.print_conflicts(after_migration)
                raise SystemExit(2)

        for rel in RUNTIME_MANIFEST:
            self.copy_file(SRC / rel, self.repo / rel)
        self.copy_rendered_file(
            SRC / 'systemd/agent-loop-scheduler.service',
            self.repo / '.agent-loop/systemd/agent-loop-scheduler.service',
            replacements={'__REPO_ROOT__': str(self.repo)},
        )
        for source_rel, destination_rel in [
            ('docs/GATEKEEPER_PROTOCOL.md', '.agent-loop/docs/GATEKEEPER_PROTOCOL.md'),
            ('docs/LOOP_BRIEF_ASSISTANT.md', '.agent-loop/docs/LOOP_BRIEF_ASSISTANT.md'),
            ('docs/LOOP_BRIEF_PATTERN_MEMORY.md', '.agent-loop/docs/LOOP_BRIEF_PATTERN_MEMORY.md'),
            ('docs/DIRECT_MODE.md', '.agent-loop/docs/DIRECT_MODE.md'),
            ('docs/COMMAND_ROUTING.md', '.agent-loop/docs/COMMAND_ROUTING.md'),
            ('docs/LOOP_INPUT_GUIDE.md', '.agent-loop/docs/LOOP_INPUT_GUIDE.md'),
            ('docs/HUMAN_SKILL_NAMESPACE.md', '.agent-loop/docs/HUMAN_SKILL_NAMESPACE.md'),
            ('docs/SOP_ROUTING.md', '.agent-loop/docs/SOP_ROUTING.md'),
            ('docs/LLM_ASSISTED_INSTALL.md', '.agent-loop/docs/LLM_ASSISTED_INSTALL.md'),
            ('docs/MERGE_RULES.md', '.agent-loop/docs/MERGE_RULES.md'),
            ('docs/SHARED_LAYOUTS.md', '.agent-loop/docs/SHARED_LAYOUTS.md'),
            ('docs/DESIGN_PHILOSOPHY.md', '.agent-loop/docs/DESIGN_PHILOSOPHY.md'),
            ('docs/ARCHITECTURE.md', '.agent-loop/docs/ARCHITECTURE.md'),
            ('docs/LEARNING_OBSERVABILITY.md', '.agent-loop/docs/LEARNING_OBSERVABILITY.md'),
            ('docs/OKF_LLMWIKI.md', '.agent-loop/docs/OKF_LLMWIKI.md'),
            ('templates/LOOP_BRIEF.md', '.agent-loop/templates/LOOP_BRIEF.md'),
            ('templates/OKF_CONCEPT.md', '.agent-loop/templates/OKF_CONCEPT.md'),
            ('templates/OKF_LOOP_BRIEF_PATTERN.md', '.agent-loop/templates/OKF_LOOP_BRIEF_PATTERN.md'),
            ('templates/SOP_SKILL_TEMPLATE.md', '.agent-loop/templates/SOP_SKILL_TEMPLATE.md'),
            ('templates/INSTALL_MERGE_REPORT.md', '.agent-loop/templates/INSTALL_MERGE_REPORT.md'),
        ]:
            self.copy_file(SRC / source_rel, self.repo / destination_rel)

        self.install_llmwiki_skeleton()

        self.merge_json(SRC / 'adapters/codex/.codex/hooks.json', self.repo / '.codex/hooks.json')
        self.merge_json(SRC / 'adapters/claude/.claude/settings.json', self.repo / '.claude/settings.json')

        if self.dry_run:
            skill_mappings = [
                (SRC / 'adapters/shared/skills', self.canonical_skill_root, 'canonical-shared')
            ]
        else:
            skill_mappings, skill_conflicts = self.skill_install_layout()
            if skill_conflicts:
                raise InstallerError('Skill layout changed after preflight.')
        mappings = [
            *skill_mappings,
            (SRC / 'adapters/codex/.codex/agents', self.repo / '.codex/agents', 'codex-agents'),
            (SRC / 'adapters/claude/.claude/agents', self.repo / '.claude/agents', 'claude-agents'),
        ]
        for source_base, target_base, layout_kind in mappings:
            if layout_kind == 'canonical-shared':
                if self.dry_run:
                    print(f'[dry-run] use canonical shared skills root {target_base}')
                else:
                    self.record('use-canonical-skill-root', None, target_base)
                    print(f'Using canonical shared skills root: {target_base}')
            for source in source_base.rglob('*'):
                if source.is_file():
                    self.copy_file(source, target_base / source.relative_to(source_base))

        snippet = (SRC / 'instruction-snippet.md').read_text(encoding='utf-8')
        self.patch_marked_file(self.repo / 'AGENTS.md', snippet)
        self.patch_marked_file(self.repo / 'CLAUDE.md', snippet)
        self.patch_gitignore()

        if not self.dry_run:
            self.build_okfctl()
            version = self.run_okfctl('version')
            if version.returncode != 0:
                raise InstallerError(f'okfctl version check failed: {version.stderr.strip() or version.stdout.strip() or "unknown error"}')
            validation = self.run_okfctl('validate', '--root', 'llmwiki')
            if validation.returncode != 0:
                raise InstallerError(f'okfctl validate failed: {validation.stderr.strip() or validation.stdout.strip() or "unknown error"}')

        if not self.dry_run:
            (self.repo / '.agent-loop/hooks/loop_hook.py').chmod(0o755)
            (self.repo / '.agent-loop/bin/learning_health.py').chmod(0o755)
            (self.repo / '.agent-loop/bin/next_turn_scheduler.py').chmod(0o755)
            (self.repo / '.agent-loop/bin/next_turn_scheduler_daemon.py').chmod(0o755)
            (self.repo / '.agent-loop/bin/okfctl').chmod(0o755)
            (self.repo / '.agent-loop/bin/build-okfctl.sh').chmod(0o755)
        self.write_install_manifest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Install Gatekeeper-first loop engineering adapters safely.'
    )
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument(
        '--conflict', choices=('error', 'backup', 'agent'), default='error',
        help=(
            'error: abort before changing anything when a path has the wrong type; '
            'backup: relocate structural conflicts into .loop-engineering-backups/<timestamp>/; '
            'agent: emit an LLM semantic-merge plan and make no repository changes.'
        ),
    )
    parser.add_argument(
        '--agent-plan-dir', type=Path,
        help='Directory for the LLM-assisted installation dossier used with --conflict agent.',
    )
    parser.add_argument(
        '--validate-only', action='store_true',
        help='Validate an existing merged installation without modifying it.',
    )
    args = parser.parse_args()
    repo = args.repo.expanduser().resolve()
    if not repo.exists():
        raise SystemExit(f'Repository not found: {repo}')
    if not repo.is_dir():
        raise SystemExit(f'Repository path is not a directory: {repo}')

    installer = Installer(repo, dry_run=args.dry_run, conflict=args.conflict)
    if args.validate_only:
        errors = installer.validate_installation()
        if errors:
            print('Installation validation failed:', file=sys.stderr)
            for item in errors:
                print(f'  - {item}', file=sys.stderr)
            return 4
        print('Installation validation succeeded.')
        return 0
    try:
        installer.install(agent_plan_dir=args.agent_plan_dir)
    except InstallerError as exc:
        print(f'Installation failed safely: {exc}', file=sys.stderr)
        print('No conflicting node was deleted. Review the backup directory and existing files.', file=sys.stderr)
        return 2

    if args.dry_run:
        print('Dry-run complete; no files were modified.')
    else:
        print('Installed direct routing, SOP routing, Gatekeeper plus Loop Brief Assistant and reusable input-pattern controls, OKF LLMWiki memory governance, learning observability, sanitized OTel telemetry, canonical root-level skills with Codex/Claude symlinks, and LLM-assisted merge guidance.')
        if installer.backup_root.exists():
            print(f'Backups: {installer.backup_root}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
