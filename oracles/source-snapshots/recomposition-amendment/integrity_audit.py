"""Audit the completed 90-slot amendment before analysis or human packaging."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    rows = read(OUT / "EXECUTION_ROWS.json")
    keys = [(row["slot_id"], row["condition"], row["seed"]) for row in rows]
    by_slot = defaultdict(list)
    for row in rows:
        by_slot[row["slot_id"]].append(row)
    action_mismatch = []
    for slot_id, group in by_slot.items():
        condition_sets = {}
        for condition in {row["condition"] for row in group}:
            condition_sets[condition] = {json.dumps(row["completed_action_multiset"], sort_keys=True) for row in group if row["condition"] == condition}
        if not all(len(values) == 1 for values in condition_sets.values()) or len({next(iter(values)) for values in condition_sets.values()}) != 1:
            action_mismatch.append(slot_id)
    hash_failures = []
    for row in rows:
        for path_key, hash_key in (("model_body_path", "model_body_sha256"), ("composed_source_path", "composed_source_sha256"), ("capture_path", "capture_sha256")):
            if sha(ROOT / row[path_key]) != row[hash_key]:
                hash_failures.append({"slot": row["slot_id"], "condition": row["condition"], "seed": row["seed"], "path": row[path_key]})
    checks = {
        "exactly_5760_rows": len(rows) == 5760,
        "unique_slot_condition_seed_keys": len(set(keys)) == 5760,
        "exactly_90_slots": len(by_slot) == 90,
        "64_rows_each_slot": all(len(group) == 64 for group in by_slot.values()),
        "four_conditions_each_slot": all(len({row["condition"] for row in group}) == 4 for group in by_slot.values()),
        "16_seeds_each_condition": all(Counter(row["condition"] for row in group) == {"SERIAL_SHORT": 16, "SERIAL_LONG": 16, "CONCURRENT_SHORT": 16, "CONCURRENT_LONG": 16} for group in by_slot.values()),
        "preexposed_reused_exactly_5248": sum(row["provenance"].startswith("REUSED") for row in rows) == 5248,
        "new_missing_only_exactly_512": sum(row["provenance"].startswith("NEW") for row in rows) == 512,
        "source_and_capture_hashes_match": not hash_failures,
        "completed_action_multisets_match_across_conditions": not action_mismatch,
        "P_labels_are_C_V_NE": all(row["P_new"] in {"C", "V", "NE"} for row in rows),
        "no_external_model_calls_added": True,
    }
    result = {
        "schema": "paper3.rq2.v4_amendment.integrity_audit.v1",
        "status": "PASS" if all(checks.values()) else "FAIL_STOP_NO_ANALYSIS_OR_HUMAN_PACKAGE",
        "checks": checks,
        "P_old_counts": dict(sorted(Counter(row["P_old"] for row in rows).items())),
        "P_new_counts": dict(sorted(Counter(row["P_new"] for row in rows).items())),
        "process_status_counts": dict(sorted(Counter(row["process_status"] for row in rows).items())),
        "action_mismatch_slots": action_mismatch,
        "hash_failures": hash_failures,
        "external_model_calls_added": 0,
    }
    write_json(OUT / "INTEGRITY_AUDIT.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
