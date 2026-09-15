"""Freeze correction-002 after tests but before offline rescoring exposed traces."""
from __future__ import annotations

import datetime
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
    gate = read(OUT / "SCORING_CORRECTION_002_GATE.json")
    if gate["status"] != "PASS" or gate["tests"] != 33:
        raise RuntimeError("SCORING_CORRECTION_002_TEST_GATE_NOT_PASS")
    old_lock = read(HERE / "SCIENTIFIC_LOCK.json")
    if old_lock["status"] != "FROZEN_TRANSPARENT_MECHANISM_SUPPLEMENT":
        raise RuntimeError("AMENDMENT_001_LOCK_NOT_FROZEN")
    forbidden = [
        OUT / "EXECUTION_ROWS_SCORING_CORRECTION_002.json",
        OUT / "SCORING_CORRECTION_002_RESCORE.json",
        OUT / "SCORING_CORRECTION_002_INTEGRITY.json",
        OUT / "RQ2_AMENDMENT_MACHINE_ANALYSIS_SCORING_CORRECTION_002.json",
    ]
    if any(path.exists() for path in forbidden):
        raise RuntimeError("CORRECTION_002_OUTCOME_ALREADY_EXISTS")
    names = (
        "build_scoring_correction_002.py",
        "EVENT_SEMANTICS_CORRECTION_002.json",
        "amended_measurement_correction_002.py",
        "test_scoring_correction_002.py",
        "rescore_correction_002.py",
        "audit_scoring_correction_002.py",
        "analyze_scoring_correction_002.py",
        "analysis_core.py",
        "ANALYSIS_PLAN.json",
        "POWER_22_FAMILY.json",
        "SCIENTIFIC_LOCK.json",
    )
    files = [HERE / name for name in names]
    files.extend([
        OUT / "SCORING_CORRECTION_002_GATE.json",
        OUT / "EXECUTION_ROWS.json",
        OUT / "INTEGRITY_AUDIT.json",
        OUT / "EXPOSURE_LEDGER.json",
    ])
    lock = {
        "schema": "paper3.rq2.v4_amendment.scoring_correction_002.lock.v1",
        "status": "FROZEN_TRANSPARENT_POST_LOCK_SCORING_CORRECTION",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "partially_outcome_exposed": True,
        "reason": "amendment-001 incorrectly required a wait-version for a B-self-produced persistent event",
        "allowed_operation": "offline rescoring of the 5760 immutable captures only",
        "candidate_executions_allowed": 0,
        "external_model_calls_allowed": 0,
        "files": [{"path": str(path.relative_to(ROOT)), "sha256": sha(path)} for path in sorted(set(files))],
    }
    write_json(HERE / "SCORING_CORRECTION_002_LOCK.json", lock)
    print(json.dumps({"status": lock["status"], "files_bound": len(lock["files"])}, indent=2))


if __name__ == "__main__":
    main()
