from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO / ".agent-loop" / "hooks" / "loop_hook.py"
LIB_PATH = REPO / ".agent-loop" / "lib"
spec = importlib.util.spec_from_file_location("loop_hook_under_test", HOOK_PATH)
assert spec is not None and spec.loader is not None

sys.path.insert(0, str(LIB_PATH))
loop_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop_hook)


class HookBannerFileTests(unittest.TestCase):
    def test_add_context_has_banner(self) -> None:
        sample = loop_hook.add_context("UserPromptSubmit", "x")["hookSpecificOutput"]["additionalContext"]
        self.assertRegex(
            sample,
            r"^\[loopeng-bootstrap v[^|]+ \| loop_hook/v0\.1-legacy \| UserPromptSubmit\] ",
        )

    def test_deny_has_banner(self) -> None:
        sample = loop_hook.deny("PreToolUse", "denied")["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertRegex(
            sample,
            r"^\[loopeng-bootstrap v[^|]+ \| loop_hook/v0\.1-legacy \| PreToolUse\] ",
        )


if __name__ == "__main__":
    unittest.main()
