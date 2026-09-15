#!/usr/bin/env python3
"""Conservative double-blind scan for project-local identity and transport tokens."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXED = [
    b"/home/" + b"ch" + b"en",
    b"/" + b"Users" + b"/",
    b"Tail" + b"scale",
    ("\u672c\u4eba" + "Mac").encode(),
    bytes.fromhex("e99988e4baaee887a3"),
    bytes.fromhex("e5908ce5ada65a"),
    b"Ch" + b"en Reviewer1",
    b"pseudonymous " + b"classmate",
]
CHANNEL = re.compile(rb"(?<![A-Za-z0-9_])human_(?:chen|z)(?![A-Za-z0-9_])")
EXCLUDED_EMAIL_SOURCE = "final-build/ieeeconf.cls"
EMAIL = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def main() -> int:
    findings = []
    if any(path.name == ".git" for path in ROOT.rglob(".git")):
        findings.append("embedded .git history")
    for path in sorted(item for item in ROOT.rglob("*") if item.is_file()):
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        for token in FIXED:
            if token in data:
                findings.append(f"{relative}: {token!r}")
        if CHANNEL.search(data):
            findings.append(f"{relative}: legacy reviewer-channel identifier")
        if relative == "final-build/main.tex" and EMAIL.search(data):
            findings.append(f"{relative}: author-contact-like email")
        if relative != EXCLUDED_EMAIL_SOURCE and relative.startswith("final-build/") and EMAIL.search(data):
            findings.append(f"{relative}: email address")
    if findings:
        print("DOUBLE_BLIND_SCAN: FAIL")
        for finding in findings:
            print(finding)
        return 1
    print("DOUBLE_BLIND_SCAN: PASS")
    print("No project-local names, host paths, device/transport markers, legacy reviewer-channel identifiers, embedded Git history, or manuscript contact emails found.")
    print("Public citation names and third-party class-file notices are intentionally outside this token scan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
