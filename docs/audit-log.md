# Audit Log

- 2026-07-03 | commit a90e649 | release audit checklist defined; journal sanitization lint passed; loop hook self-test passed; test suite passed under current environment; manual evidence references were verified in the companion docs.
- 2026-07-03 | commit 6181c8c | okfctl binary distribution removed in favor of install-time Go build; wrapper and build script no longer manage checksums; install self-sufficiency tests passed; journal self-test stays out of .agent-loop/runtime/; full test suite passed via `python3 -m unittest discover -s tests -q` because `pytest` was unavailable here.
