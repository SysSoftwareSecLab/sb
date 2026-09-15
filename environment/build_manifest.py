#!/usr/bin/env python3
"""Seal the anonymous export after all derived files are finalized."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "MANIFEST.sha256.json"
EXCLUDED = {
    "MANIFEST.sha256.json",
    "results/final-revalidation/LOCAL_REVALIDATION.json",
}


def main() -> None:
    records = {}
    for path in sorted(item for item in ROOT.rglob("*") if item.is_file()):
        relative = path.relative_to(ROOT).as_posix()
        if relative in EXCLUDED:
            continue
        records[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    OUTPUT.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(f"sealed {len(records)} files")


if __name__ == "__main__":
    main()
