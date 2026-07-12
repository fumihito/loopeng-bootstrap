#!/usr/bin/env python3
"""Phase 1 extension gate: role-independence, DEPRECATE, report limits.

Covers blind spots of gate 1 (R1-R3). Verbatim-committed; do not edit.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase1_gate import VALID_DOC, _apply, _mk_bundle  # noqa: E402


def _doc(title: str) -> str:
    return VALID_DOC.replace('title: "Gate"', f'title: "{title}"')


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bundle = _mk_bundle(root)

        # R1a: validation must not depend on a role field
        r = _apply(root, {"operations": [{"action": "UPSERT", "proposal_id": "x1",
                                          "concept_id": "concepts/no-role", "document": _doc("NoRole")}]}, bundle)
        if not r.get("ok"):
            errors.append(f"R1a: role-less valid report rejected: {r}")

        # R1b: legacy brief-pattern namespace must be gone for every role value
        for role in ("brief-pattern-curator", "memory-curator", None):
            payload = {"operations": [{"action": "UPSERT", "proposal_id": f"x2-{role}",
                                       "concept_id": "loop-brief-patterns/p1", "document": _doc("BP")}]}
            if role:
                payload["role"] = role
            r = _apply(root, payload, bundle)
            if r.get("ok"):
                errors.append(f"R1b: loop-brief-patterns accepted (role={role})")

        # R2a: DELETE must be rejected
        _apply(root, {"operations": [{"action": "UPSERT", "proposal_id": "x3",
                                      "concept_id": "concepts/keep", "document": _doc("Keep")}]}, bundle)
        r = _apply(root, {"operations": [{"action": "DELETE", "proposal_id": "x4",
                                          "concept_id": "concepts/keep"}]}, bundle)
        if r.get("ok") or not (bundle / "concepts/keep.md").exists():
            errors.append("R2a: DELETE accepted or file physically removed")

        # R2b: DEPRECATE flips status and keeps the file
        r = _apply(root, {"operations": [{"action": "DEPRECATE", "proposal_id": "x5",
                                          "concept_id": "concepts/keep"}]}, bundle)
        text = (bundle / "concepts/keep.md").read_text(encoding="utf-8") if (bundle / "concepts/keep.md").exists() else ""
        if not r.get("ok") or not any(m in text for m in ('status: "deprecated"', "status: deprecated", "status: 'deprecated'")):
            errors.append(f"R2b: DEPRECATE missing or status not flipped: {r}")

        # R3a: proposal_id required and unique
        r = _apply(root, {"operations": [{"action": "UPSERT",
                                          "concept_id": "concepts/no-pid", "document": _doc("NoPid")}]}, bundle)
        if r.get("ok"):
            errors.append("R3a: missing proposal_id accepted")
        r = _apply(root, {"operations": [
            {"action": "UPSERT", "proposal_id": "dup", "concept_id": "concepts/d1", "document": _doc("D1")},
            {"action": "UPSERT", "proposal_id": "dup", "concept_id": "concepts/d2", "document": _doc("D2")},
        ]}, bundle)
        if r.get("ok"):
            errors.append("R3a: duplicate proposal_id accepted")

        # R3b: more than 20 operations rejected
        ops = [{"action": "UPSERT", "proposal_id": f"m{i}",
                "concept_id": f"concepts/m{i}", "document": _doc(f"M{i}")} for i in range(21)]
        r = _apply(root, {"operations": ops}, bundle)
        if r.get("ok"):
            errors.append("R3b: 21 operations accepted")

        # R3c: oversized document rejected
        big = _doc("Big") + ("x" * 70000)
        r = _apply(root, {"operations": [{"action": "UPSERT", "proposal_id": "big",
                                          "concept_id": "concepts/big", "document": big}]}, bundle)
        if r.get("ok"):
            errors.append("R3c: >64KiB document accepted")

    status = "PASS" if not errors else "FAIL"
    print(f"[{status}] gate 7: R1-R3 apply semantics")
    for line in errors:
        print(f"        - {line}")
    print()
    print("EXT GATE: " + ("GREEN" if not errors else "RED"))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
