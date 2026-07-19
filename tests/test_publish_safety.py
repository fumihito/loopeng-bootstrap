from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from utils import check_publish_safety


class PublishSafetyTests(unittest.TestCase):
    def test_ignored_untracked_files_are_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
            ignored = root / "ignored" / "cert.pem"
            ignored.parent.mkdir()
            ignored.write_text("-----BEGIN " + "PRIVATE KEY-----\n", encoding="utf-8")

            findings, suppressed = check_publish_safety.scan_with_suppressions(root)

            self.assertEqual(findings, [])
            self.assertEqual(suppressed, [])

    def test_tracked_file_is_scanned_even_when_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
            tracked = root / "ignored" / "cert.pem"
            tracked.parent.mkdir()
            tracked.write_text("-----BEGIN " + "PRIVATE KEY-----\n", encoding="utf-8")
            subprocess.run(["git", "add", "-f", str(tracked)], cwd=root, check=True)

            findings, suppressed = check_publish_safety.scan_with_suppressions(root)

            self.assertEqual(suppressed, [])
            self.assertEqual(
                {finding.message for finding in findings},
                {
                    "suspicious file name: private key or certificate file",
                    "private key block",
                },
            )

    def test_sensitive_assignment_comment_is_reported_as_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "fixture.py"
            source.write_text(
                'message = "password=SUPER-SECRET-VALUE"  # publish-safety: ignore sensitive assignment\n',
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                status = check_publish_safety.main(["--root", str(root)])

            self.assertEqual(status, 0)
            self.assertIn(
                "SUPPRESSED: fixture.py:1: sensitive assignment "
                "[message = \"password=<redacted>] "
                "[publish-safety: ignore sensitive assignment]",
                output.getvalue(),
            )
            self.assertIn("OK: no obvious credentials or risky secrets found", output.getvalue())

    def test_redacted_assignment_is_not_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            redacted_value = "<redacted>" + "=<redacted>"
            (root / "report.md").write_text(
                "password=" + redacted_value + "\n", encoding="utf-8"
            )

            findings, suppressed = check_publish_safety.scan_with_suppressions(root)

            self.assertEqual(findings, [])
            self.assertEqual(suppressed, [])


if __name__ == "__main__":
    unittest.main()
