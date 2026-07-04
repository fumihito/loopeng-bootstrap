# Scheduler

This repository uses a deterministic next-turn handoff file and a polling daemon to close the loop between completed turns and the next prompt submission.

For the autonomy readiness checklist that answers when the loop actually runs, see `docs/GATEKEEPER_PROTOCOL.md`.

## Responsibilities

- `next_turn_scheduler.py` reads or validates a completed turn's `next-turn.json` handoff.
- `next_turn_scheduler_daemon.py` polls for ready handoffs and invokes the configured trigger or notification command.
- `trigger_command` is for the actual next-turn execution path.
- `notification_command` is for non-executing side effects such as dry-run logging or alerts.

The daemon already re-checks the handoff state before it invokes a command. Trigger helpers should not repeat cadence or readiness gating.

## Policy example

```json
{
  "enabled": true,
  "poll_interval_seconds": 5,
  "trigger_command": [
    "./.agent-loop/bin/trigger-example.sh"
  ],
  "notification_command": [
    "./.agent-loop/bin/trigger-dryrun.sh"
  ],
  "trigger_command_timeout_seconds": 30,
  "record_events": true
}
```

The repository ships the two example helpers above so a clean install can demonstrate the scheduler boundary end to end:

- `trigger-example.sh` reads `gatekeeper-prompt.txt`, which is the sole prompt-text source of truth, and launches the next headless Claude turn from the repository root.
- `trigger-dryrun.sh` appends one JSON record to `.agent-loop/runtime/scheduler/trigger-dryrun.log` and exits.

Verified by `tests/test_loop_e2e_two_turns.py::LoopE2ETwoTurnTests` and `tests/test_smoke.py::IntegrationTest.test_scheduler_daemon_triggers_ready_handoff_once`.

The daemon still exposes `gatekeeper_prompt_path` for metadata JSON and `gatekeeper_prompt_text_path` for the plain-text prompt body.

## Timeout and failure behavior

- If `trigger_command` times out or exits non-zero, the daemon records a `trigger_failed` event and keeps polling.
- If `notification_command` times out or exits non-zero, the daemon records a `notification_failed` event and keeps polling.
- Trigger and notification commands are best-effort side effects; they do not replace the deterministic handoff file.

## Systemd

The installed systemd unit points at the persistent daemon and is intended for a user service that stays alive between turns. The daemon's final-cycle summary is emitted separately from `events.jsonl` so `systemctl status` has a human-readable snapshot.
