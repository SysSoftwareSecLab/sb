"""Hash-lock amendment inputs after the executable gate and before missing-trace completion."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V4 = HERE.parent / "rq2_structure_preserving_recomposition_v4"
SOURCE_RUN = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4"
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
    gate = read(OUT / "PREEXECUTION_GATE.json")
    if gate["status"] != "PASS" or (OUT / "EXECUTION_ROWS.json").exists():
        raise RuntimeError("PREEXECUTION_GATE_NOT_CLEAN")
    qualification = read(OUT / "AMENDED_ATOMIC_QUALIFICATION.json")
    eligible_ids = {row["slot_id"] for row in qualification["rows"] if row["eligible"]}
    manifest = read(V4 / "GENERATION_MANIFEST.json")
    files = [
        path for path in HERE.iterdir()
        if path.is_file() and path.name != "SCIENTIFIC_LOCK.json"
    ]
    files.extend([
        OUT / "EXPOSURE_LEDGER.json",
        OUT / "AMENDED_ATOMIC_QUALIFICATION.json",
        OUT / "MEASUREMENT_GATE.json",
        OUT / "ANALYSIS_SEMANTICS_TESTS.json",
        OUT / "PREEXECUTION_GATE.json",
        V4 / "SCIENTIFIC_FREEZE.json",
        V4 / "GENERATION_MANIFEST.json",
        SOURCE_RUN / "POSTMODEL_ELIGIBILITY_GATE.json",
    ])
    for slot in manifest:
        if slot["slot_id"] in eligible_ids:
            folder = SOURCE_RUN / "generation" / slot["slot_id"]
            files.extend([folder / "candidate.py", folder / "RESULT.json"])
    files = sorted(set(files))
    lock = {
        "schema": "paper3.rq2.v4_amendment.scientific_lock.v1",
        "status": "FROZEN_TRANSPARENT_MECHANISM_SUPPLEMENT",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "partially_outcome_exposed": True,
        "preexposed_rows": 5248,
        "eligible_slots": 90,
        "main_common_families": 22,
        "maximum_rows": 5760,
        "external_model_calls_added": 0,
        "files": [{"path": str(path.relative_to(ROOT)), "sha256": sha(path)} for path in files],
    }
    write_json(HERE / "SCIENTIFIC_LOCK.json", lock)
    print(json.dumps({"status": lock["status"], "files_bound": len(files), "eligible_slots": 90, "maximum_rows": 5760}, indent=2))


if __name__ == "__main__":
    main()
