#!/usr/bin/env bash
set -euo pipefail

: "${runtime_dir:?runtime_dir is required}"

python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

runtime_dir = Path(os.environ["runtime_dir"])
runtime_dir.mkdir(parents=True, exist_ok=True)
record = {
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "scheduler_action": os.environ.get("scheduler_action", "dryrun"),
    "repo": os.environ.get("repo"),
    "turn_id": os.environ.get("turn_id"),
    "session_id": os.environ.get("session_id"),
    "handoff_path": os.environ.get("handoff_path"),
    "gatekeeper_prompt_path": os.environ.get("gatekeeper_prompt_path"),
    "trigger_kind": os.environ.get("trigger_kind"),
    "trigger_cadence": os.environ.get("trigger_cadence"),
}
with (runtime_dir / "trigger-dryrun.log").open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
PY
