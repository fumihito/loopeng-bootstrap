#!/usr/bin/env python3
"""Verify that the declared runtime distribution is complete and safe."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


DEV_ONLY_PREFIXES = ("tests/", "docs/", "adapters/", "utils/")
DEV_ONLY_UTILS = {"utils/audit_guard.py", "utils/phase1_gate.py", "utils/phase1_gate_ext.py"}


def _installer(root: Path):
    spec = importlib.util.spec_from_file_location("loopeng_install_for_lint", root / "install.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load install.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def lint(root: Path) -> list[str]:
    root = root.resolve()
    module = _installer(root)
    errors: list[str] = []
    planned = [source.relative_to(root).as_posix() for source, _ in module.Installer(
        root, dry_run=True, conflict="error", profile=module.PROFILE_FULL
    ).runtime_distribution_sources()]
    planned_set = set(planned)
    for package in module.EXPECTED_DISTRIBUTED_PACKAGES:
        package_root = root / package
        for source in sorted(package_root.rglob("*.py")):
            rel = source.relative_to(root).as_posix()
            if rel not in planned_set:
                errors.append(f"package module is not in full distribution plan: {rel}")
    for rel in planned:
        if not (root / rel).is_file():
            errors.append(f"distribution plan references missing path: {rel}")
    for rel in planned:
        if rel.startswith(DEV_ONLY_PREFIXES) and rel not in {"utils/skill_structure_lint.py"}:
            errors.append(f"development-only path is distributed: {rel}")
    for rel in DEV_ONLY_UTILS:
        if rel in planned_set:
            errors.append(f"development-only utility is distributed: {rel}")
    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the declared full distribution plan.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    errors = lint(args.root)
    if errors:
        print("distribution lint: FAIL")
        print("\n".join(errors))
        return 1
    print("distribution lint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
