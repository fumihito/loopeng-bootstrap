# Canonical Shared Skills Layout

## Normative layout

Codex and Claude Code must consume one physical skill tree at the repository root:

```text
{ROOT}/skills/
{ROOT}/.agents/skills -> ../skills/
{ROOT}/.claude/skills -> ../skills/
```

`skills/` must be a real directory, not a symlink. Both platform aliases must be symbolic links whose stored target is exactly `../skills/`. This is the only supported post-install layout.

## Why one physical tree

Maintaining independent Codex and Claude copies creates configuration drift: one role can gain different instructions, safety constraints, or telemetry rules depending on the client that invokes it. A shared physical file makes role identity a filesystem invariant rather than a synchronization convention.

Platform-specific behavior belongs in `.codex/agents/*.toml`, `.claude/agents/*.md`, hook adapters, or runtime context. It must not be encoded by forking the shared `SKILL.md`.

## Skill editing policy

For distributed frame skills, `adapters/shared/skills/` is the sole edit point.
The root `skills/` tree is an installed/generated result and must not be edited
directly. After changing a shared skill, run `python3 install.py --self --update`
before validation or commit so the installed tree and manifest are regenerated
from the adapter source.

## Deterministic migration

The installer handles these legacy forms before copying package files:

1. Missing aliases: create `.agents/skills` and `.claude/skills` as `../skills/` symlinks.
2. Existing aliases with another internal target: merge readable files into `{ROOT}/skills`, preserve the old link in the timestamped backup tree, and repoint it.
3. Physical platform skill directories: move each directory to the backup tree, merge its contents into `{ROOT}/skills`, then replace it with the canonical symlink.
4. A symlink at `{ROOT}/skills`: materialize a real directory, copy the internal target's contents, and preserve the original link target as JSON metadata under the backup tree. Symlink nodes are not placed at mirrored backup paths because later file backups must never traverse them.
5. Known package-managed skill collisions: retain all legacy copies in backup and install the current `adapters/shared/skills` version.
6. Unknown same-relative-path files with different contents: stop before mutation because the intended semantic merge cannot be inferred deterministically.

Unrelated existing skills are preserved. Nested symlinks inside skill trees and links resolving outside the repository are rejected.

## Validation invariants

`install.py --validate-only` checks all of the following:

- `{ROOT}/skills` is a real directory;
- both platform aliases are symlinks;
- each stored target is exactly `../skills/`;
- both aliases resolve to `{ROOT}/skills`;
- each role and SOP is present in `{ROOT}/skills`;
- the Codex-visible, Claude-visible, and canonical paths refer to the same file.

The install manifest records `create-canonical-skill-link`, `consolidate-platform-skill-root`, and `use-canonical-skill-root` actions as applicable.
