# Install

v0.2 keeps the installer focused on the remaining frame-* skill family and the shared runtime scaffolding.

## Profiles

### Full

```bash
python3 install.py --repo /path/to/repository
```

### Routing

```bash
python3 install.py --repo /path/to/repository --profile routing
```

The routing profile installs the frame-* skills and the files needed for local routing and audit checks. It does not install the removed loop-control skills, OKF engine artifacts, or old v0.1 role docs.

### Global dispatcher

Install a `loopeng` command that dispatches to the nearest managed repository:

```bash
python3 install.py --install-command
python3 install.py --install-command /custom/bin
```

The dispatcher searches upward from the current directory for `loopeng/__main__.py` and runs that repository's `loopeng.py` (falling back to `python3 -m loopeng` if the launcher is absent). It does not modify shell startup files. An existing command is preserved and causes exit 2; use `--force` to replace it. If the destination directory is not on `PATH`, the installer reports that fact without editing any rc file.

### Self update

```bash
python3 install.py --repo .
python3 install.py --self --update
```

Use the self-update flow from the repository root when you are updating the kit from itself.

## Layout rule

`adapters/shared/skills/` is the source of truth for shared skills. `install.py --self --update` is the distribution path. In v0.2, only frame-* skills remain in the shared skill set.

## Distribution boundary and integrity

The full profile distributes the complete `loopeng/` Python package, `loopeng.py`,
`VERSION`, `utils/skill_structure_lint.py`, the frame-* skills, state templates,
and hook sidecars. Tests, development gates and lints, documentation, and
adapter source remain kit-only. Each installation records the exact payload in
`.agent-loop/runtime/install-manifest.json`; `python3 -m loopeng doctor` checks
that payload and the installed version. Use `doctor --against /path/to/kit`
when the source kit is available.

`python3 install.py --repo /path/to/repository --update --dry-run` prints the
planned payload changes without modifying the repository. Re-running an update
from the same kit is idempotent and reports no payload changes.

To verify the routing metadata for every shared frame skill, run
`python3 utils/routing_hints_lint.py --root .`. The check is also part of the
completion audit, so a missing or malformed `routing.md` blocks `record`.

## Hooks

Installation registers the managed hook entry points for Claude Code and Codex
under their respective repository configuration. With hooks enabled, events
are journaled automatically and hard blocks are enforced before execution;
hooks-disabled operation remains a supported degraded mode. The invariants
and platform boundaries are defined in `docs/ARCHITECTURE.md`.
