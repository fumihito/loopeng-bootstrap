#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


IGNORED_DIR_NAMES = {".git"}
MAX_READ_BYTES = 2 * 1024 * 1024

HIGH_CONFIDENCE_FILE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(^|/)\.env(\.[^/]+)?$"), ".env file"),
    (re.compile(r"(?i)(^|/)\.npmrc$"), ".npmrc file"),
    (re.compile(r"(?i)(^|/)\.netrc$"), ".netrc file"),
    (re.compile(r"(?i)(^|/)\.pypirc$"), ".pypirc file"),
    (re.compile(r"(?i)(^|/)(id_rsa|id_dsa|id_ecdsa|id_ed25519)$"), "private key file"),
    (re.compile(r"(?i)(^|/).*\.(pem|key|p12|pfx|der)$"), "private key or certificate file"),
    (re.compile(r"(?i)(^|/)(credentials|secrets?|secret[_-]?config)(\..*)?$"), "credentials file"),
    (re.compile(r"(?i)(^|/).*service[-_]?account.*\.json$"), "service account file"),
    (re.compile(r"(?i)(^|/)\.docker/config\.json$"), "docker config file"),
]

PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")
EMBEDDED_CREDENTIALS_RE = re.compile(r"(?i)\bhttps?://[^/\s:@]+:[^/\s:@]+@")
AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
AWS_TEMP_KEY_RE = re.compile(r"\bASIA[0-9A-Z]{16}\b")
GITHUB_PAT_RE = re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")
GITHUB_TOKEN_RE = re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")
AUTH_HEADER_RE = re.compile(r"(?i)\b(?:authorization|proxy-authorization)\s*[:=]\s*(?:bearer|basic)\s+[A-Za-z0-9\-._~+/=]{20,}")
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:password|passwd|token|api[_-]?key|client[_-]?secret|private[_-]?key|access[_-]?key|refresh[_-]?token|session[_-]?token|aws[_-]?secret[_-]?access[_-]?key|aws[_-]?access[_-]?key)\b\s*[:=]\s*(['\"]?)([^'\"\s]{8,})\1"
)


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int | None
    severity: str
    message: str
    evidence: str | None = None

    def render(self, root: Path) -> str:
        rel = self.path.relative_to(root)
        location = f"{rel}"
        if self.line is not None:
            location = f"{location}:{self.line}"
        if self.evidence:
            return f"{self.severity}: {location}: {self.message} [{self.evidence}]"
        return f"{self.severity}: {location}: {self.message}"


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return files


def file_name_finding(path: Path, root: Path) -> Finding | None:
    rel = path.relative_to(root).as_posix()
    for pattern, message in HIGH_CONFIDENCE_FILE_PATTERNS:
        if pattern.search(rel):
            return Finding(path=path, line=None, severity="ERROR", message=f"suspicious file name: {message}")
    return None


def looks_textual(data: bytes) -> bool:
    if not data:
        return True
    if b"\x00" in data:
        return False
    sample = data[:4096]
    if not sample:
        return True
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        textish = sum(1 for b in sample if b in b"\t\n\r\f\v" or 32 <= b <= 126)
        return textish / len(sample) >= 0.9


def secretish(value: str) -> bool:
    if len(value) < 12:
        return False
    if any(ch.isspace() for ch in value):
        return False
    classes = {
        "lower": any(ch.islower() for ch in value),
        "upper": any(ch.isupper() for ch in value),
        "digit": any(ch.isdigit() for ch in value),
        "symbol": any(not ch.isalnum() for ch in value),
    }
    return sum(classes.values()) >= 2 or re.fullmatch(r"[A-Fa-f0-9]{24,}", value) is not None or re.fullmatch(r"[A-Za-z0-9+/=]{24,}", value) is not None


def line_findings(path: Path, root: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    patterns: list[tuple[str, re.Pattern[str], bool]] = [
        ("private key block", PRIVATE_KEY_RE, False),
        ("embedded credentials in URL", EMBEDDED_CREDENTIALS_RE, False),
        ("AWS access key id", AWS_ACCESS_KEY_RE, False),
        ("AWS temporary access key", AWS_TEMP_KEY_RE, False),
        ("GitHub personal access token", GITHUB_TOKEN_RE, False),
        ("GitHub fine-grained token", GITHUB_PAT_RE, False),
        ("OpenAI secret key", OPENAI_KEY_RE, False),
        ("Slack token", SLACK_TOKEN_RE, False),
        ("Google API key", GOOGLE_API_KEY_RE, False),
        ("sensitive authorization header", AUTH_HEADER_RE, False),
        ("sensitive assignment", SENSITIVE_ASSIGNMENT_RE, True),
    ]

    for line_no, line in enumerate(text.splitlines(), start=1):
        for message, pattern, needs_secretish in patterns:
            match = pattern.search(line)
            if not match:
                continue
            if needs_secretish:
                value = match.group(2)
                if not secretish(value):
                    continue
                prefix = line[: match.start(2)]
                if prefix.endswith(("=", ":")):
                    evidence = f"{prefix}<redacted>"
                else:
                    evidence = "<redacted>"
            else:
                evidence = "<redacted>"
            findings.append(
                Finding(
                    path=path,
                    line=line_no,
                    severity="ERROR",
                    message=message,
                    evidence=evidence,
                )
            )
    return findings


def scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root):
        file_finding = file_name_finding(path, root)
        if file_finding is not None:
            findings.append(file_finding)

        try:
            data = path.read_bytes()
        except OSError as exc:
            findings.append(Finding(path=path, line=None, severity="ERROR", message=f"unable to read file: {exc}"))
            continue

        if len(data) > MAX_READ_BYTES:
            data = data[:MAX_READ_BYTES]

        if not looks_textual(data):
            continue

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")

        findings.extend(line_findings(path, root, text))
    return findings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan the repository for credentials and risky secrets before publishing.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root to scan. Defaults to the current directory.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.root.resolve()

    if not root.exists() or not root.is_dir():
        print(f"ERROR: root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2

    findings = scan(root)
    if not findings:
        print(f"OK: no obvious credentials or risky secrets found under {root}")
        return 0

    print(f"Found {len(findings)} potential issue(s) under {root}:")
    for finding in findings:
        print(finding.render(root))
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
