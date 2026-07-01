# Semantic merge rules

These rules define how an installation agent should combine the package with an existing repository.

## General precedence

1. Preserve user-owned behavior and data.
2. Add package behavior without duplicating it.
3. Preserve the stricter security, privacy, approval, and sandbox boundary.
4. Prefer reversible changes and explicit adapters over destructive replacement.
5. Escalate irreducible ambiguity rather than inventing a mapping.

## JSON hooks and settings

- Parse both documents as JSON objects.
- Preserve every unrelated top-level key.
- The `hooks` value must remain an object whose event values are arrays.
- Remove only hook groups whose serialized content contains `.agent-loop/hooks/loop_hook.py`; these are package-managed predecessors.
- Append the current package groups once, preserving existing unrelated group order.
- For `env`, preserve existing keys except the package privacy keys, where the safe values take precedence:
  - `OTEL_LOG_USER_PROMPTS=0`
  - `OTEL_LOG_TOOL_DETAILS=0`
  - `OTEL_LOG_TOOL_CONTENT=0`
  - `OTEL_LOG_RAW_API_BODIES=0`
- If an existing value has a different type, stop and request a decision rather than coercing it.

## Markdown instruction files

- Preserve all existing text outside the managed markers.
- Replace an existing complete managed block.
- If only one marker exists, stop: the file is ambiguous.
- Do not move unrelated instructions into the managed block.

## Skills and subagents

- Compare frontmatter identity, purpose, tools, permissions, sandbox mode, and output contract.
- If both files implement the same package role, preserve stricter permissions and merge non-conflicting project-specific instructions.
- If the existing component has a different purpose despite the same path/name, rename it to a clear project-specific name and update all references only when this can be proven safe.
- Never merge two independent roles into one prompt merely to avoid a filename conflict.

## Recognized mixed-client layouts

The deterministic installer handles these layouts before semantic merge:

- `{ROOT}/skills` is the only real skill tree.
- `.agents/skills` and `.claude/skills` are normalized to exact `../skills/` symlinks.
- Existing physical platform skill directories are backed up and deterministically consolidated into `{ROOT}/skills`.
- Unknown same-path skill files with different contents require semantic review; do not choose one arbitrarily.
- A regular `.codex` file that is valid UTF-8 TOML is migrated byte-for-byte to `.codex/config.toml`, with the original preserved in the backup tree.

Do not undo these migrations during semantic merge. Review the manifest and merge only project-specific meaning that is not already preserved.

## Unrecognized structural conflicts

For other file-versus-directory conflicts:

- Determine whether the file is an active configuration, a legacy artifact, or unrelated data.
- Back it up intact.
- Migrate recognized settings to their supported destinations.
- Preserve unrecognized material under `.loop-engineering-legacy/<original-name>` and report it.
- Never infer credentials or print values while migrating.
- Reject any skill-root symlink that resolves outside the repository.

## Managed core files

The hook runner, package policy, OTel schema, and package documentation are versioned package components. If no local changes exist, replace them after backup. If local changes exist, identify the extension intent and port it explicitly. Do not silently carry forward modifications that weaken controls.

## Verification

A merge is successful only when `install.py --validate-only` succeeds and a human-readable diff confirms that unrelated configuration remains intact.

## OKF LLMWiki merge rules

- Treat `llmwiki/` as project-owned durable knowledge, not a managed directory to replace wholesale.
- Create only missing skeleton `index.md`, `log.md`, and standard category directories during installation.
- Never overwrite, rename, delete, or normalize an existing concept merely because the package contains a template or newer skeleton.
- Before changing an existing concept, use the normal memory proposal, Meta-Evaluator, Memory Curator, and deterministic `okfctl apply-report` path.
- Preserve unknown OKF frontmatter fields when semantically merging a concept.
- Do not copy raw legacy logs, prompts, tool results, credentials, or configuration contents into LLMWiki.
- Run `.agent-loop/bin/okfctl validate --root llmwiki` after installation. Validation failure is a merge issue, not permission to discard project knowledge.
