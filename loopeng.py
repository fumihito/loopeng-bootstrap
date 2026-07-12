#!/usr/bin/env python3
"""Launcher for loopeng. Equivalent to `python3 -m loopeng` at the repo root."""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.argv[0] = "loopeng"
runpy.run_module("loopeng", run_name="__main__", alter_sys=True)
