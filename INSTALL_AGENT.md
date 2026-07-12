# LLM-assisted installation

This guide describes the v0.2 installation flow for an existing repository.
The deterministic installer performs the profile migration; an LLM-assisted
step is only for inspecting and semantically merging project-owned material.

## Procedure

1. Run `python3 install.py --repo <repository> --profile full --update` (or
   `--profile routing` when only the frame-* skills are required).
2. Read the generated migration report and inspect any preserved backup under
   `.loop-engineering-backups/<timestamp>/`.
3. Preserve unrelated hooks, instructions, policies, skills, and LLMWiki
   content. Merge only project-specific behavior into the current v0.2
   destinations; do not restore retired v0.1 Gatekeeper, Loop Brief, or Go
   runtime artifacts.
4. Run `python3 install.py --repo <repository> --validate-only` and then the
   repository's tests before claiming installation complete.

`adapters/shared/skills/` is the source of truth for distributed frame-* skills;
after changing a frame skill, run `python3 install.py --self --update` so the
installed tree and manifest converge. See [docs/INSTALL.md](docs/INSTALL.md)
and [docs/MERGE_RULES.md](docs/MERGE_RULES.md) for the operational details.
