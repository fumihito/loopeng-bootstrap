# Installation

This document covers the supported install profiles, canonical mixed-client layout, and the LLM-assisted semantic merge workflow.

## Prerequisites

- Full install: Go 1.21+.
- Routing profile: no Go-backed loop layer is required.
- All installs assume a writable target repository and a Python 3 runtime for `install.py`.

## Supported profiles

### Full loop install

```bash
python3 install.py --repo /path/to/repository
```

This installs the autonomous loop, OKF LLMWiki support, scheduler artifacts, and the full guardrail set.

### Routing profile

```bash
python3 install.py --repo /path/to/repository --profile routing
```

This installs the bounded routing layer for `direct:`, `route:`, `frame-*`, and SOP entrypoints without the autonomous loop machinery.

### Self-apply

```bash
python3 install.py --repo .
```

Run this from the repository you want to equip. It is the same installer entrypoint, just pointed at the current tree.

## Mixed Codex / Claude layout

The canonical post-install skill layout is one real `{ROOT}/skills` directory with `.agents/skills` and `.claude/skills` as `../skills/` symlinks. The installer also migrates a legacy `.codex` TOML file to `.codex/config.toml` when the file is valid UTF-8 TOML.

See `docs/SHARED_LAYOUTS.md` for the exact migration and validation rules.

## Semantic merge workflow

When structural conflicts or same-name skill collisions require human review, generate an install dossier instead of guessing:

```bash
python3 install.py --repo /path/to/repository --conflict agent --agent-plan-dir /safe/path/install-plan
```

The semantic merge flow preserves existing behavior, backs up conflicting files, and asks the installer agent to resolve only what the deterministic installer cannot safely infer. The authoritative procedure is described in `docs/LLM_ASSISTED_INSTALL.md` and `docs/MERGE_RULES.md`.

## Validation

After installation, validate with:

```bash
python3 install.py --repo /path/to/repository --validate-only
```

For OKF memory validation, run:

```bash
.agent-loop/bin/okfctl validate --root llmwiki
```

If the target repository uses developer hook automation, `utils/install-dev-hooks.sh` can enable the pre-push audit guard.
