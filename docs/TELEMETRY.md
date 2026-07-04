# Telemetry

## Purpose

The hook layer emits sanitized OpenTelemetry events so the repository can observe routing, role selection, command names, and turn outcomes without logging prompts or other sensitive content.

## Contract

The project records only structural facts such as:

- platform (`claude` or `codex`)
- role or subagent name
- invoked skill name when observable
- tool name
- executable command name(s)
- success or failure
- duration when supplied by the host
- mutation epoch
- watchdog state
- aggregate learning-health counts or ratios

It does not emit raw prompts, command strings, command arguments, file paths, URLs, search patterns, tool input, tool output, hook headers, environment variables, credentials, problem signatures, lesson IDs, lesson text, question IDs, or evidence references.

## Collector

A local debug collector example is available at `.agent-loop/otel-collector.yaml`.

```bash
otelcol-contrib --config .agent-loop/otel-collector.yaml
```

The default endpoint is `http://127.0.0.1:4318/v1/logs`. Override it with `AGENT_LOOP_OTEL_ENDPOINT` and `AGENT_LOOP_OTEL_HEADERS` when you need to point at a different collector.

## Self-test

Telemetry self-tests run through the hook layer and verify the redaction contract:

```bash
python3 .agent-loop/hooks/loop_hook.py telemetry-test --platform claude
python3 .agent-loop/hooks/loop_hook.py telemetry-test --platform codex
```

If no collector is listening, a sanitized fallback record is written to `.agent-loop/runtime/telemetry.jsonl`.
