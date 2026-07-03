#!/usr/bin/env bash
set -euo pipefail

: "${repo:?repo is required}"
: "${gatekeeper_prompt_text_path:?gatekeeper_prompt_text_path is required}"

if ! command -v claude >/dev/null 2>&1; then
  echo "trigger-example.sh requires the claude CLI on PATH" >&2
  exit 127
fi

if [[ ! -f "$gatekeeper_prompt_text_path" ]]; then
  echo "gatekeeper prompt not found: $gatekeeper_prompt_text_path" >&2
  exit 2
fi

cd "$repo"
exec claude -p "$(cat "$gatekeeper_prompt_text_path")"
