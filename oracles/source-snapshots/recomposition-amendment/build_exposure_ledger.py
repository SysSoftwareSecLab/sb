"""Inventory every already-materialized v4 factorial artifact without trusting status files."""
from __future__ import annotations

from collections import Counter, defaultdict
import datetime
import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE_RUN = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4"
OUT = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    base = SOURCE_RUN / "factorial_execution"
    artifacts = []
    per_slot = defaultdict(lambda: {"conditions": defaultdict(set), "artifact_count": 0})
    result_labels = Counter()
    for path in sorted(base.rglob("*")) if base.exists() else []:
        if not path.is_file() or path.name not in {"CAPTURE.json", "RESULT.json", "composed.py"}:
            continue
        relative = path.relative_to(ROOT)
        parts = path.relative_to(base).parts
        slot = parts[0] if len(parts) >= 1 else None
        condition = parts[1] if len(parts) >= 2 else None
        seed_text = parts[2] if len(parts) >= 3 else None
        seed = int(seed_text.removeprefix("seed_")) if seed_text and seed_text.startswith("seed_") else None
        stat = path.stat()
        row = {
            "path": str(relative),
            "sha256": sha(path),
            "mtime_ns": stat.st_mtime_ns,
            "bytes": stat.st_size,
            "slot_id": slot,
            "condition": condition,
            "seed": seed,
            "artifact_type": path.name,
        }
        if path.name == "RESULT.json":
            try:
                result = json.loads(path.read_text(encoding="utf-8"))
                row["P"] = result.get("P")
                row["process_status"] = result.get("process_status")
                result_labels[str(result.get("P"))] += 1
            except Exception as error:
                row["parse_error"] = type(error).__name__
        artifacts.append(row)
        if slot:
            per_slot[slot]["artifact_count"] += 1
            if condition and seed is not None:
                per_slot[slot]["conditions"][condition].add(seed)

    slot_rows = []
    for slot, item in sorted(per_slot.items()):
        condition_counts = {name: len(seeds) for name, seeds in sorted(item["conditions"].items())}
        result_count = sum(1 for row in artifacts if row["slot_id"] == slot and row["artifact_type"] == "RESULT.json")
        slot_rows.append({
            "slot_id": slot,
            "outcome_exposed": result_count > 0,
            "artifact_count": item["artifact_count"],
            "result_count": result_count,
            "condition_seed_counts": condition_counts,
            "complete_64_results": result_count == 64,
        })
    ledger = {
        "schema": "paper3.rq2.v4_amendment.exposure_ledger.v1",
        "captured_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "recursive filesystem inventory; LIMITED_STATUS not trusted",
        "outcome_exposed_definition": "at least one factorial RESULT.json existed at ledger time",
        "artifact_types": ["composed.py", "CAPTURE.json", "RESULT.json"],
        "artifact_count": len(artifacts),
        "result_count": sum(row["artifact_type"] == "RESULT.json" for row in artifacts),
        "capture_count": sum(row["artifact_type"] == "CAPTURE.json" for row in artifacts),
        "composed_source_count": sum(row["artifact_type"] == "composed.py" for row in artifacts),
        "slot_directory_count": len(slot_rows),
        "outcome_exposed_slots": sum(row["outcome_exposed"] for row in slot_rows),
        "complete_64_result_slots": sum(row["complete_64_results"] for row in slot_rows),
        "partial_result_slots": [row for row in slot_rows if row["outcome_exposed"] and not row["complete_64_results"]],
        "P_labels_at_ledger_time": dict(sorted(result_labels.items())),
        "slots": slot_rows,
        "artifacts": artifacts,
    }
    write_json(OUT / "EXPOSURE_LEDGER.json", ledger)
    print(json.dumps({key: ledger[key] for key in (
        "captured_utc", "artifact_count", "result_count", "capture_count",
        "composed_source_count", "slot_directory_count", "outcome_exposed_slots",
        "complete_64_result_slots", "partial_result_slots", "P_labels_at_ledger_time",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
