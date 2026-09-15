"""Freeze the runner after its all-reference standard-item test."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


P = Path(__file__).resolve().parent
ROOT = P.parents[3]
RUN = ROOT / "05_formal/rq2_rq4_identifiable_confirmation_v1"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size}


def main() -> None:
    output = P / "EXECUTION_IMPLEMENTATION_FREEZE_V3.json"
    if output.exists():
        raise RuntimeError("V3 execution implementation already frozen")
    capability_responses = list((RUN / "capability_v2").glob("*/RESPONSE.raw")) if (RUN / "capability_v2").exists() else []
    natural_responses = list((RUN / "generation").glob("*/RESPONSE.raw")) if (RUN / "generation").exists() else []
    assert not capability_responses and not natural_responses
    assert read(P / "ACTIVE_COLLECTION_GATE.json")["status"] == "ACTIVE_AFTER_PRECALL_POWER_CLARIFICATION"
    files = [
        P / "ACTIVE_COLLECTION_GATE.json", P / "IMPLEMENTATION_REVISION_002.json", P / "freeze_execution_v3.py",
        P / "run_natural.py", P / "package_human_review.py", P / "HUMAN_REVIEW_GUIDE.md",
        P.parent / "formal_replacement_v2/collect.py", P.parent / "formal_replacement_v2/PUBLIC_API.md",
        P.parent.parent / "trace_dev_v1/runtime.py",
        ROOT / "01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src/geometry_interface_v01.py",
        ROOT / "01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src/dynamic_geometry_v01.py",
        P.parent.parent / "task2_evidence/evaluate.py", P.parent / "structural_batch/measure.py",
        P.parent.parent / "batch_7_9/evidence.py",
    ]
    value = {
        "status": "FROZEN_BEFORE_NATURAL_CALLS_AFTER_REFERENCE_STANDARD_TEST",
        "scientific_model_calls_before_freeze": 0,
        "natural_slots": 320,
        "reference_standard_test": {"references": 80, "S0_S1_S2_T_P_all_C": 80, "false_structure_V_after_revision": 0},
        "capability_results_required_before_natural": True,
        "execute_and_write_exposure_before_next_model_request": True,
        "historical_execution_freezes_retained": ["EXECUTION_IMPLEMENTATION_FREEZE.json", "EXECUTION_IMPLEMENTATION_FREEZE_V2.json"],
        "files": [record(path) for path in sorted(files)]
    }
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": value["status"], "natural_slots": 320, "scientific_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
