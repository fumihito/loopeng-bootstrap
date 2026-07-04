---
name: sop-list
description: Mandatory mode index for prompts beginning with list:. Enumerate the current user-entry modes and route families from the canonical repository sources.
---

# SOP: Mode index

Use this SOP when the routing hook loads `sop-list` from a leading `list:` header.

## Objective

Return the current user-entry mode families in a form a human can scan quickly. This is a discovery surface, not a control surface.

## Procedure

1. Read the canonical routing sources:
   - `docs/DIRECT_MODE.md`
   - `docs/SOP_ROUTING.md`
   - `docs/HUMAN_SKILL_NAMESPACE.md`
   - `docs/LOOP_INPUT_GUIDE.md`
   - the `SKILL.md` files under `adapters/shared/skills/sop-*/`
   - the `SKILL.md` files under `adapters/shared/skills/frame-*/`
2. Derive the currently available entry modes from those sources.
3. Group the result by family:
   - `direct:` for bounded non-autonomous turns
   - `list:` for this discovery mode
   - `sop-<header>:` for mandatory SOPs
   - `frame-<name>:` for human-facing frames
   - no prefix for the autonomous-loop / Gatekeeper path
4. Report the current names and a one-line purpose for each.
5. If a family grows, reflect the new names from the sources instead of relying on a hardcoded list.

## Output

Return a concise mode index with:

- mode family
- trigger prefix
- current names
- one-line purpose

Do not invent unavailable modes. If a source is missing, say which source was unavailable and list the remaining authoritative sources.
