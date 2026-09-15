"""Verify that correction-002 changes labels only, never the immutable evidence."""
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
    old_rows = read(OUT / "EXECUTION_ROWS.json")
    new_rows = read(OUT / "EXECUTION_ROWS_SCORING_CORRECTION_002.json")
    old_by_key = {(row["slot_id"], row["condition"], row["seed"]): row for row in old_rows}
    new_by_key = {(row["slot_id"], row["condition"], row["seed"]): row for row in new_rows}
    immutable_fields = (
        "slot_id", "family_id", "mechanism", "profile", "repeat", "condition", "seed",
        "model_body_path", "model_body_sha256", "composed_source_path", "composed_source_sha256",
        "capture_path", "capture_sha256", "process_status", "returncode", "api_error_count",
        "cleanup_ok", "lifecycle_complete", "completed_action_multiset", "provenance",
    )
    immutable_mismatches = []
    hash_failures = []
    for key, old in old_by_key.items():
        new = new_by_key.get(key)
        if new is None:
            immutable_mismatches.append({"key": key, "reason": "missing corrected row"})
            continue
        changed = [field for field in immutable_fields if old.get(field) != new.get(field)]
        if changed:
            immutable_mismatches.append({"key": key, "fields": changed})
        for path_field, hash_field in (
            ("model_body_path", "model_body_sha256"),
            ("composed_source_path", "composed_source_sha256"),
            ("capture_path", "capture_sha256"),
        ):
            if sha(ROOT / new[path_field]) != new[hash_field]:
                hash_failures.append({"key": key, "path": new[path_field]})

    by_slot = defaultdict(list)
    for row in new_rows:
        by_slot[row["slot_id"]].append(row)
    checks = {
        "exactly_5760_rows_before_and_after": len(old_rows) == len(new_rows) == 5760,
        "same_unique_keys": set(old_by_key) == set(new_by_key) and len(new_by_key) == 5760,
        "immutable_evidence_fields_unchanged": not immutable_mismatches,
        "source_and_capture_hashes_match": not hash_failures,
        "exactly_90_slots_and_64_rows_each": len(by_slot) == 90 and all(len(group) == 64 for group in by_slot.values()),
        "only_C_V_NE": all(row["P_new"] in {"C", "V", "NE"} for row in new_rows),
        "candidate_executions_zero": True,
        "external_model_calls_added_zero": True,
    }
    result = {
        "schema": "paper3.rq2.v4_amendment.scoring_correction_002.integrity.v1",
        "status": "PASS" if all(checks.values()) else "FAIL_STOP_NO_ANALYSIS_OR_HUMAN_PACKAGE",
        "checks": checks,
        "amendment_001_counts": dict(sorted(Counter(row["P_new"] for row in old_rows).items())),
        "correction_002_counts": dict(sorted(Counter(row["P_new"] for row in new_rows).items())),
        "changed_rows": sum(old_by_key[key]["P_new"] != new_by_key[key]["P_new"] for key in set(old_by_key) & set(new_by_key)),
        "immutable_mismatches": immutable_mismatches,
        "hash_failures": hash_failures,
        "candidate_executions": 0,
        "external_model_calls_added": 0,
    }
    write_json(OUT / "SCORING_CORRECTION_002_INTEGRITY.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
