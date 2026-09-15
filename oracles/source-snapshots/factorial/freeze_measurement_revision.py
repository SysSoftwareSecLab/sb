"""Freeze transparent measurement revision 001 before resuming natural calls."""
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
    destination = P / "MEASUREMENT_REVISION_FREEZE.json"
    if destination.exists():
        raise RuntimeError("Measurement revision already frozen")
    revision = read(P / "MIDSTREAM_MEASUREMENT_REVISION_001.json")
    capability_gate = read(P / "CAPABILITY_INTERPRETATION_GATE_AFTER_RESULTS.json")
    reference = read(RUN / "measurement_revision_001/REFERENCE_VALIDATION.json")
    immutability = read(RUN / "measurement_revision_001/LEGACY_IMMUTABILITY_MANIFEST.json")
    assert revision["status"] == "DEFINED_BEFORE_RESUMING_NATURAL_COLLECTION"
    assert capability_gate["status"] == "FROZEN_AFTER_CAPABILITY_AND_BEFORE_NATURAL_RESUME"
    assert reference == {
        "status": "PASS", "references": 80, "S0_S1_S2_and_P_direct_base_all_C": 80,
        "false_structure_fidelity_V": 0, "model_or_factor_aggregate_direction_examined": False,
    }
    assert immutability["remeasured_slots"] == 103 and immutability["legacy_files_preserved"] == 206
    for item in immutability["legacy_files"]:
        path = ROOT / item["path"]
        assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"]
    results = list((RUN / "generation").glob("*/RESULT.json"))
    ledgers = list((RUN / "evidence").glob("*/EXPOSURE_LEDGER_V2.json"))
    summaries = list((RUN / "evidence").glob("*/SUMMARY_V2.json"))
    base_evidence = list((RUN / "evidence").glob("*/BASE_TASK_EVIDENCE_V2.json"))
    assert len(results) == len(ledgers) == len(summaries) == len(base_evidence) == 103
    bad_stage = []
    for path in ledgers:
        ledger = read(path)
        stages = tuple(ledger[key]["verdict"] for key in ["S0_source_entry", "S1_api", "S2_robot_contract"])
        if ledger["P_direct_base"]["verdict"] == "V" and stages != ("C", "C", "C"):
            bad_stage.append(str(path.relative_to(ROOT)))
    assert not bad_stage
    unresolved_receipts = sorted(
        str(receipt.relative_to(ROOT)) for receipt in (RUN / "generation").glob("*/RECEIPT.json")
        if not (receipt.parent / "RESULT.json").exists()
    )
    assert unresolved_receipts == [
        "05_formal/rq2_rq4_identifiable_confirmation_v1/generation/I-IC04_C4_ALLOCATION-BOUND-SERIAL-SHORT-glm46/RECEIPT.json"
    ]
    inputs = [
        P / "MIDSTREAM_MEASUREMENT_REVISION_001.json", P / "MIDSTREAM_MEASUREMENT_REVISION_001.md",
        P / "CAPABILITY_INTERPRETATION_GATE_AFTER_RESULTS.json", P / "remeasure_exposure_v2.py",
        P / "run_natural_v2.py", P / "HUMAN_REVIEW_GUIDE_V2.md", P / "package_human_review_v2.py",
        P / "deliver_to_mac_v2.py", P / "run_natural.py", P / "package_human_review.py",
        RUN / "CAPABILITY_RESULTS_V2.json", RUN / "measurement_revision_001/REFERENCE_VALIDATION.json",
        RUN / "measurement_revision_001/LEGACY_IMMUTABILITY_MANIFEST.json",
    ]
    destination.write_text(json.dumps({
        "status": "FROZEN_BEFORE_NATURAL_RESUME",
        "measurement_revision": "RQ2_RQ4_IDENTIFIABLE_CONFIRMATION_MEASUREMENT_001",
        "completed_natural_slots": 103, "remaining_natural_slots": 217,
        "one_unresolved_transport_receipt": unresolved_receipts[0],
        "unresolved_transport_rule": "Retry the same frozen slot under delivery-unknown recovery; it is not a new scientific slot.",
        "reference_validation": reference, "legacy_files_verified_unchanged": 206,
        "P_direct_base_V_without_all_stage_C": 0,
        "model_or_factor_aggregate_direction_examined_for_revision": False,
        "tasks_requests_models_sample_and_stop_unchanged": True,
        "resume_decision": "QUALIFIED_TO_RESUME_REMAINING_FROZEN_SLOTS",
        "files": [record(path) for path in inputs],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "MEASUREMENT_REVISION_FROZEN", "complete": 103, "remaining": 217}, ensure_ascii=False))

if __name__ == "__main__":
    main()
