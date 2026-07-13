from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from ._paths import agent_root

LOCK_WAIT_SEC = 30
POLL_SEC = 0.05


def _lock_path(repo: Path) -> Path:
    return repo / agent_root("state", "lock")


def _stale(path: Path) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        pid = int(value.get("pid", 0))
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        return True
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return True


@contextmanager
def repo_lock(repo: Path, run_id: str = "unknown") -> Iterator[None]:
    repo = repo.resolve()
    path = _lock_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_WAIT_SEC
    stale_recovered = False
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"pid": os.getpid(), "run_id": run_id, "acquired_at": datetime.now(timezone.utc).isoformat()}, handle)
            break
        except FileExistsError:
            if _stale(path):
                try:
                    path.unlink()
                    stale_recovered = True
                    continue
                except FileNotFoundError:
                    continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"repository lock wait exceeded {LOCK_WAIT_SEC}s: {path}")
            time.sleep(POLL_SEC)
    try:
        if stale_recovered:
            # Keep the recovery auditable without making journal availability
            # a prerequisite for the mutation itself.
            from .journal import EVENT_COMMAND, append_event
            try:
                append_event(repo, run_id, {"kind": EVENT_COMMAND, "command": "stale repository lock recovered"})
            except OSError:
                pass
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
