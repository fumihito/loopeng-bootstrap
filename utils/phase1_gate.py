#!/usr/bin/env python3
"""Phase 1 exit gate for loopeng-bootstrap v0.2 self-hosting.

Executable acceptance for SA-WP1..SA-WP5. This script is the ONLY
authority for declaring Phase 1 complete. It is expected to be RED
until the corresponding work packages are implemented.

Usage:
    python3 utils/phase1_gate.py            # run all gates
    python3 utils/phase1_gate.py --gate 1   # run a single gate

Exit code 0 iff every gate passes. Not discovered by unittest on
purpose: it must be runnable while red without breaking the suite.

Design rule: gates only observe externally visible behaviour
(CLI invocations, file system, report text). They never import
implementation internals, so they cannot be satisfied by renaming
or by tests that assert the absence of things that never existed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

LEGACY_ARTIFACTS = (
    ".agent-loop/hooks/loop_hook.py",
    ".agent-loop/lib/loop_gate.py",
    ".agent-loop/policy.json",
    ".agent-loop/sop-policy.json",
    ".agent-loop/direct-policy.json",
    ".agent-loop/otel.json",
    ".agent-loop/otel-collector.yaml",
    "routing_hints.py",
)

VALID_DOC = """---
type: "Concept"
title: "Gate"
description: "Gate check concept"
tags: ["gate"]
timestamp: "2026-07-10T00:00:00Z"
status: "active"
sensitivity: "internal"
authority: "phase1-gate"
confidence: "1.0"
---

# Gate
Gate check document.
"""


def _run(args: list[str], cwd: Path, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, env=env)


def _loopeng(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run([PY, "-m", "loopeng", *args], cwd=cwd)


def _mk_bundle(root: Path) -> Path:
    bundle = root / "llmwiki"
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "index.md").write_text("# i\n", encoding="utf-8")
    (bundle / "log.md").write_text("# l\n", encoding="utf-8")
    return bundle


def _mk_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "gate@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "gate"], check=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)
    return repo


def _apply(cwd: Path, payload: dict, bundle: Path) -> dict:
    report = cwd / "gate-report.json"
    report.write_text(json.dumps(payload), encoding="utf-8")
    proc = _loopeng(cwd, "okf", "apply", str(report), "--bundle", str(bundle), "--backup-dir", str(cwd / "bk"))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": proc.returncode == 0, "raw": proc.stdout + proc.stderr}


# ---------------------------------------------------------------- gates

def gate1_memory_gate() -> list[str]:
    """SA-WP1: apply rejects schema-invalid documents and path escapes."""
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bundle = _mk_bundle(root)
        # D1: document without frontmatter must be rejected
        r = _apply(root, {"operations": [{"action": "UPSERT", "proposal_id": "p1",
                                          "concept_id": "concepts/junk", "document": "no frontmatter"}]}, bundle)
        if r.get("ok"):
            errors.append("D1 open: schema-invalid document accepted")
        # D2: traversal must be rejected and must not write outside bundle
        r = _apply(root, {"operations": [{"action": "UPSERT", "proposal_id": "p2",
                                          "concept_id": "../escaped", "document": VALID_DOC}]}, bundle)
        if r.get("ok") or (root / "escaped.md").exists():
            errors.append("D2 open: concept_id traversal accepted or escaped file written")
        # namespace: unknown top directory must be rejected
        r = _apply(root, {"operations": [{"action": "UPSERT", "proposal_id": "p3",
                                          "concept_id": "elsewhere/x", "document": VALID_DOC}]}, bundle)
        if r.get("ok"):
            errors.append("namespace: concept_id outside allowed type dirs accepted")
        # control: a valid document must still be accepted
        r = _apply(root, {"operations": [{"action": "UPSERT", "proposal_id": "p4",
                                          "concept_id": "concepts/gate-ok", "document": VALID_DOC}]}, bundle)
        if not r.get("ok"):
            errors.append(f"control: valid document rejected: {r}")
        # okf init must exist and produce a valid bundle
        proc = _loopeng(root, "okf", "init", str(root / "wiki2"))
        if proc.returncode != 0:
            errors.append("okf init missing or failing")
        else:
            proc = _loopeng(root, "okf", "validate", str(root / "wiki2"))
            if proc.returncode != 0:
                errors.append("okf init produced an invalid bundle")
    return errors


def gate2_run_scoping() -> list[str]:
    """SA-WP2: pre-existing dirty paths are not attributed to a run."""
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        repo = _mk_repo(Path(td))
        (repo / "pre-dirty.txt").write_text("dirty before run\n", encoding="utf-8")
        run_id = "gate-scope"
        _loopeng(repo, "journal", "add", "--run", run_id, "--repo", str(repo),
                 "--event", json.dumps({"kind": "run-start", "agent": "gate", "summary": "scope"}))
        _loopeng(repo, "journal", "add", "--run", run_id, "--repo", str(repo),
                 "--event", json.dumps({"kind": "run-end"}))
        _loopeng(repo, "audit", "run", "--run", run_id, "--repo", str(repo))
        report = repo / ".agent-loop/state/reports" / f"{run_id}.md"
        if not report.is_file():
            return ["audit run produced no report"]
        text = report.read_text(encoding="utf-8")
        if "pre-dirty.txt" in text:
            errors.append("S3 open: pre-existing dirty path attributed to the run")
    return errors


def gate3_intent_discrimination() -> list[str]:
    """SA-WP3: declared protected-path change -> warn; undeclared -> critical."""
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        repo = _mk_repo(Path(td))
        (repo / "AGENTS.md").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "agents"], check=True)

        # declared run
        run_id = "gate-declared"
        _loopeng(repo, "journal", "add", "--run", run_id, "--repo", str(repo),
                 "--event", json.dumps({"kind": "run-start", "agent": "gate", "summary": "declared"}))
        _loopeng(repo, "journal", "add", "--run", run_id, "--repo", str(repo),
                 "--event", json.dumps({"kind": "intent", "paths": ["AGENTS.md"], "reason": "gate"}))
        (repo / "AGENTS.md").write_text("changed\n", encoding="utf-8")
        _loopeng(repo, "journal", "add", "--run", run_id, "--repo", str(repo),
                 "--event", json.dumps({"kind": "mutation", "path": "AGENTS.md"}))
        _loopeng(repo, "journal", "add", "--run", run_id, "--repo", str(repo),
                 "--event", json.dumps({"kind": "run-end"}))
        _loopeng(repo, "audit", "run", "--run", run_id, "--repo", str(repo))
        declared = (repo / ".agent-loop/state/reports" / f"{run_id}.md")
        if not declared.is_file():
            return ["audit run produced no report (declared case)"]
        dtext = declared.read_text(encoding="utf-8")
        if "CRITICAL ALERTS PRESENT" in dtext:
            errors.append("S2 open: declared protected-path change still raises the critical banner")

        # undeclared run (fresh clone state)
        subprocess.run(["git", "-C", str(repo), "checkout", "-q", "--", "AGENTS.md"], check=True)
        run_id2 = "gate-undeclared"
        _loopeng(repo, "journal", "add", "--run", run_id2, "--repo", str(repo),
                 "--event", json.dumps({"kind": "run-start", "agent": "gate", "summary": "undeclared"}))
        (repo / "AGENTS.md").write_text("changed again\n", encoding="utf-8")
        _loopeng(repo, "journal", "add", "--run", run_id2, "--repo", str(repo),
                 "--event", json.dumps({"kind": "mutation", "path": "AGENTS.md"}))
        _loopeng(repo, "journal", "add", "--run", run_id2, "--repo", str(repo),
                 "--event", json.dumps({"kind": "run-end"}))
        _loopeng(repo, "audit", "run", "--run", run_id2, "--repo", str(repo))
        utext = (repo / ".agent-loop/state/reports" / f"{run_id2}.md").read_text(encoding="utf-8")
        if "CRITICAL ALERTS PRESENT" not in utext:
            errors.append("discrimination lost: undeclared protected-path change no longer critical")
    return errors


def gate4_install_v02() -> list[str]:
    """SA-WP4: full profile is Go-free, ships loopeng, no v0.1 artifacts; self-update works."""
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        target = _mk_repo(Path(td))
        proc = _run([PY, str(REPO / "install.py"), "--repo", str(target), "--profile", "full"], cwd=REPO)
        if proc.returncode != 0:
            errors.append(f"full profile install failed: {proc.stdout[-200:]} {proc.stderr[-200:]}")
        else:
            if "Go 1.21" in proc.stdout + proc.stderr:
                errors.append("full profile still mentions a Go requirement")
            if not (target / "loopeng" / "cli.py").is_file():
                errors.append("loopeng package not distributed to target")
            present = [rel for rel in LEGACY_ARTIFACTS if (target / rel).exists()]
            if present:
                errors.append(f"v0.1 artifacts redistributed: {present}")
        # self-update on a scratch copy of the kit itself
        kit_copy = Path(td) / "kit"
        shutil.copytree(REPO, kit_copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        subprocess.run(["git", "init", "-q"], cwd=kit_copy, check=True)
        proc = _run([PY, str(kit_copy / "install.py"), "--repo", ".", "--self", "--update"], cwd=kit_copy)
        if proc.returncode != 0 or "Go 1.21" in proc.stdout + proc.stderr:
            errors.append("S1 open: Go-free self-update fails")
    return errors


def gate5_handoff_chain() -> list[str]:
    """SA-WP5: run 1 writes a handoff that run 2's schedule next consumes."""
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        repo = _mk_repo(Path(td))
        run_id = "gate-run1"
        _loopeng(repo, "journal", "add", "--run", run_id, "--repo", str(repo),
                 "--event", json.dumps({"kind": "run-start", "agent": "gate", "goal": "chain"}))
        _loopeng(repo, "journal", "add", "--run", run_id, "--repo", str(repo),
                 "--event", json.dumps({"kind": "run-end"}))
        _loopeng(repo, "audit", "run", "--run", run_id, "--repo", str(repo))
        handoff = repo / ".agent-loop/state/handoff.json"
        if not handoff.is_file():
            errors.append("D4 open: audit run does not write handoff.json")
            return errors
        proc = _loopeng(repo, "schedule", "next", "--repo", str(repo))
        out = proc.stdout
        if "No handoff available" in out or run_id not in out:
            errors.append("D4 open: schedule next does not consume the previous run's handoff")
        report = (repo / ".agent-loop/state/reports" / f"{run_id}.md").read_text(encoding="utf-8")
        if "agent-type: unknown" in report or "- handoff: none" in report:
            errors.append("Run Report still contains placeholder fields")
    return errors


def gate6_unit_suite() -> list[str]:
    proc = _run([PY, "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=REPO)
    if proc.returncode != 0:
        return ["unit test suite failing: " + proc.stderr.strip().splitlines()[-1]]
    return []


GATES = {
    1: ("SA-WP1 memory gate (D1/D2/namespace/init)", gate1_memory_gate),
    2: ("SA-WP2 run scoping (S3)", gate2_run_scoping),
    3: ("SA-WP3 intent discrimination (S2)", gate3_intent_discrimination),
    4: ("SA-WP4 install v0.2 + Go-free self-update (D3/S1)", gate4_install_v02),
    5: ("SA-WP5 handoff chain + report data (D4)", gate5_handoff_chain),
    6: ("unit suite green", gate6_unit_suite),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", type=int, choices=sorted(GATES))
    args = parser.parse_args()
    selected = [args.gate] if args.gate else sorted(GATES)
    failures = 0
    for key in selected:
        title, fn = GATES[key]
        try:
            errors = fn()
        except Exception as exc:  # a crashing gate is a failing gate
            errors = [f"gate crashed: {exc!r}"]
        status = "PASS" if not errors else "FAIL"
        print(f"[{status}] gate {key}: {title}")
        for line in errors:
            print(f"        - {line}")
        failures += bool(errors)
    print()
    if failures:
        print(f"PHASE 1 GATE: RED ({failures} gate(s) failing) — self-application not permitted")
        return 1
    print("PHASE 1 GATE: GREEN — self-application permitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
