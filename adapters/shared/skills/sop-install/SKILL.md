---
name: sop-install
description: Mandatory semantic-merge installation procedure for prompts beginning with install:.
---

# SOP: LLM-assisted installation

Deterministic-first execution is mandatory.

Use this SOP only to install or upgrade the Loop Engineering package while preserving existing Codex, Claude Code, hook, skill, agent, policy, and instruction configuration.

1. Locate the unpacked package root and the target repository.
2. Read `<package-root>/README.md`, `<package-root>/docs/SHARED_LAYOUTS.md`, and `<package-root>/docs/MERGE_RULES.md`.
3. Run a dry run first:

```bash
python3 <package-root>/install.py --repo <target-repository> --dry-run
```

4. If the output contains only recognized migrations, run the normal deterministic installer without a conflict flag. Recognized migrations include repository-internal shared skills symlinks and a valid legacy `.codex` TOML file.
5. If an unrecognized conflict remains, generate an LLM-assisted plan instead of relocating it blindly:

```bash
python3 <package-root>/install.py \
  --repo <target-repository> \
  --conflict agent \
  --agent-plan-dir <safe-plan-directory>
```

6. Follow the generated `INSTALL_AGENT.md` exactly for semantic conflicts. Back up every changed or relocated node.
7. Never expose configuration values, credentials, prompts, command arguments, or tool inputs in chat, logs, or reports.
8. Validate the final installation:

```bash
python3 <package-root>/install.py --repo <target-repository> --validate-only
```

9. Review Git diff and the install manifest. Return `COMPLETE` only when validation succeeds and no unresolved semantic conflict remains.
