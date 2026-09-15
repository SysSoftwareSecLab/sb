"""Offline rescore all 5760 immutable captures; do not execute candidates."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from amended_measurement_correction_002 import evaluate, schedule_hash


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V4 = HERE.parent / "rq2_structure_preserving_recomposition_v4"
OUT = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"


def read(path: Path): return json.loads(path.read_text(encoding="utf-8"))
def sha(path: Path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path: Path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    rows = read(OUT / "EXECUTION_ROWS.json")
    rescored = []
    for row in rows:
        capture_path = ROOT / row["capture_path"]
        if sha(capture_path) != row["capture_sha256"]:
            raise RuntimeError("CAPTURE_CHANGED:" + row["capture_path"])
        spec = read(V4 / "reference_tasks" / row["family_id"] / "SPEC.json")
        endpoint = evaluate(read(capture_path), spec)
        updated = dict(row)
        updated["P_amendment_001"] = row["P_new"]
        updated["P_amendment_001_reason"] = row["P_new_reason"]
        updated["P_new"] = endpoint["P"]
        updated["P_new_exposed"] = endpoint["exposed"]
        updated["P_new_reason"] = endpoint["reason"]
        updated["persistent_state_audit_correction_002"] = endpoint.get("persistent_state_audit")
        updated["measurement_revision"] = "SCORING_CORRECTION_002"
        updated["schedule_hash_new"] = schedule_hash(read(capture_path))
        rescored.append(updated)
    write_json(OUT / "EXECUTION_ROWS_SCORING_CORRECTION_002.json", rescored)
    result = {
        "schema": "paper3.rq2.v4_amendment.scoring_correction_002.rescore.v1",
        "status": "COMPLETE",
        "rows": len(rescored),
        "amendment_001_counts": dict(sorted(Counter(row["P_amendment_001"] for row in rescored).items())),
        "correction_002_counts": dict(sorted(Counter(row["P_new"] for row in rescored).items())),
        "changed_rows": sum(row["P_amendment_001"] != row["P_new"] for row in rescored),
        "candidate_executions": 0,
        "external_model_calls_added": 0,
    }
    write_json(OUT / "SCORING_CORRECTION_002_RESCORE.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
