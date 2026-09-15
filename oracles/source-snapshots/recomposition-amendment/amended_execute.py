"""Complete only missing v4 traces and rescore all 90 eligible slots under amendment 001."""
from __future__ import annotations

import asyncio
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V4 = HERE.parent / "rq2_structure_preserving_recomposition_v4"
SOURCE_RUN = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4"
OUT = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"
QUALITY = V4.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
sys.path.insert(0, str(V4))
from runtime import execute
from frozen_composer import SEEDS, audit_four_conditions, compose
import direct_p_oracle as original_oracle
from amended_measurement import evaluate, schedule_hash


CONDITIONS = (("SERIAL", "SHORT"), ("SERIAL", "LONG"), ("CONCURRENT", "SHORT"), ("CONCURRENT", "LONG"))


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def verify_lock() -> None:
    lock = read(HERE / "SCIENTIFIC_LOCK.json")
    if lock["status"] != "FROZEN_TRANSPARENT_MECHANISM_SUPPLEMENT":
        raise RuntimeError("AMENDMENT_LOCK_NOT_ACTIVE")
    for item in lock["files"]:
        if sha(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError("AMENDMENT_LOCK_FILE_CHANGED:" + item["path"])


def cleanup_ok(capture: dict, spec: dict) -> bool:
    events = capture.get("trusted_events", [])
    scene = events[-1].get("scene_state", {}) if events else {}
    goals = {key: value for key, value in spec["pair_constants"]["goals"].items() if key not in {"LEFT", "RIGHT"}}
    poses = spec["world"]["pose_coordinates_m"]
    return (
        scene.get("gripper_xyz_m", {}).get("LEFT") == poses["left_home"]
        and scene.get("gripper_xyz_m", {}).get("RIGHT") == poses["right_home"]
        and not scene.get("resource_owners", {})
        and not scene.get("active_events", {})
        and scene.get("held", {}) == {"LEFT": None, "RIGHT": None}
        and not scene.get("stopped_arms", [])
        and scene.get("active_failure") is None
        and all(scene.get("objects", {}).get(object_id) == destination for object_id, destination in goals.items())
    )


def completed_action_multiset(capture: dict) -> dict:
    return dict(sorted(Counter(
        event["action"] for event in capture.get("trusted_events", [])
        if event.get("phase") == "complete" and event.get("action") != "run_return"
    ).items()))


async def main() -> None:
    verify_lock()
    qualification = read(OUT / "AMENDED_ATOMIC_QUALIFICATION.json")
    if qualification["status"] != "PASS_EXPECTED_90" or qualification["eligible_slots"] != 90:
        raise RuntimeError("AMENDED_ATOMIC_GATE_FAILED")
    eligible_ids = {row["slot_id"] for row in qualification["rows"] if row["eligible"]}
    manifest = [row for row in read(V4 / "GENERATION_MANIFEST.json") if row["slot_id"] in eligible_ids]
    if len(manifest) != 90:
        raise RuntimeError("ELIGIBLE_MANIFEST_NOT_90")
    catalog = {row["family_id"]: row for row in read(V4 / "REFERENCE_TASK_CATALOG.json")}
    ledger = read(OUT / "EXPOSURE_LEDGER.json")
    ledger_hashes = {row["path"]: row["sha256"] for row in ledger["artifacts"]}
    rows = []
    reused = 0
    created = 0
    for slot_index, slot in enumerate(manifest, 1):
        verify_lock()
        source_path = SOURCE_RUN / "generation" / slot["slot_id"] / "candidate.py"
        source = source_path.read_text(encoding="utf-8")
        spec = read(V4 / catalog[slot["family_id"]]["spec_path"])
        composer_audit = audit_four_conditions(source, 0, slot["serial_policy"])
        if not composer_audit["passed"]:
            raise RuntimeError("COMPOSER_AUDIT_FAILED:" + slot["slot_id"])
        for schedule, distance in CONDITIONS:
            condition = schedule + "_" + distance
            for seed in SEEDS:
                source_folder = SOURCE_RUN / "factorial_execution" / slot["slot_id"] / condition / f"seed_{seed:02d}"
                source_files = [source_folder / "composed.py", source_folder / "CAPTURE.json", source_folder / "RESULT.json"]
                exists = [path.exists() for path in source_files]
                if any(exists) and not all(exists):
                    raise RuntimeError("PARTIAL_PREEXISTING_TRACE:" + slot["slot_id"] + ":" + condition + ":" + str(seed))
                if all(exists):
                    for path in source_files:
                        relative = str(path.relative_to(ROOT))
                        if relative not in ledger_hashes or sha(path) != ledger_hashes[relative]:
                            raise RuntimeError("PREEXISTING_ARTIFACT_CHANGED_OR_NOT_LEDGERED:" + relative)
                    composed_path, capture_path, old_result_path = source_files
                    capture = read(capture_path)
                    old_result = read(old_result_path)
                    old_endpoint = {"P": old_result["P"], "exposed": old_result["P_exposed"], "reason": old_result["P_reason"]}
                    provenance = "REUSED_HASH_BOUND_PRE_AMENDMENT_TRACE"
                    reused += 1
                else:
                    folder = OUT / "factorial_execution_new" / slot["slot_id"] / condition / f"seed_{seed:02d}"
                    composed_path = folder / "composed.py"
                    capture_path = folder / "CAPTURE.json"
                    old_result_path = None
                    composed = compose(source, schedule, distance, seed, slot["serial_policy"])
                    write_text(composed_path, composed)
                    capture = await execute(composed, spec, ROOT)
                    write_json(capture_path, capture)
                    old_endpoint = original_oracle.evaluate(capture, spec)
                    provenance = "NEW_EXECUTION_FOR_PREVIOUSLY_ABSENT_TRACE_ONLY"
                    created += 1
                amended = evaluate(capture, spec)
                row = {
                    "slot_id": slot["slot_id"], "family_id": slot["family_id"],
                    "mechanism": slot["mechanism"], "profile": slot["profile"], "repeat": slot["repeat"],
                    "schedule": schedule, "distance": distance, "condition": condition, "seed": seed,
                    "provenance": provenance,
                    "lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
                    "process_status": capture.get("process", {}).get("status"),
                    "returncode": capture.get("process", {}).get("returncode"),
                    "api_error_count": len(capture.get("trusted_api_errors", [])),
                    "cleanup_ok": cleanup_ok(capture, spec),
                    "P_old": old_endpoint["P"], "P_old_exposed": old_endpoint["exposed"], "P_old_reason": old_endpoint["reason"],
                    "P_new": amended["P"], "P_new_exposed": amended["exposed"], "P_new_reason": amended["reason"],
                    "persistent_state_audit": amended.get("persistent_state_audit"),
                    "schedule_hash_new": schedule_hash(capture),
                    "completed_action_multiset": completed_action_multiset(capture),
                    "model_body_path": str(source_path.relative_to(ROOT)),
                    "model_body_sha256": sha(source_path),
                    "composed_source_path": str(composed_path.relative_to(ROOT)),
                    "composed_source_sha256": sha(composed_path),
                    "capture_path": str(capture_path.relative_to(ROOT)),
                    "capture_sha256": sha(capture_path),
                    "old_result_path": str(old_result_path.relative_to(ROOT)) if old_result_path else None,
                    "old_result_sha256": sha(old_result_path) if old_result_path else None,
                }
                result_path = OUT / "rescored" / slot["slot_id"] / condition / f"seed_{seed:02d}" / "RESULT_AMENDMENT_001.json"
                write_json(result_path, row)
                rows.append(row)
        write_json(OUT / "EXECUTION_ROWS.partial.json", rows)
        write_json(OUT / "STATUS.json", {
            "phase": "AMENDMENT_EXECUTION", "slot_complete": slot_index, "slot_total": 90,
            "rows": len(rows), "reused_preexposed": reused, "new_missing_only": created,
            "external_model_calls_added": 0,
        })
        print(json.dumps({"slot": slot["slot_id"], "n": slot_index, "total": 90, "rows": len(rows), "reused": reused, "new": created}), flush=True)
    write_json(OUT / "EXECUTION_ROWS.json", rows)
    write_json(OUT / "STATUS.json", {
        "phase": "AMENDMENT_EXECUTION_COMPLETE", "eligible_slots": 90,
        "rows": len(rows), "reused_preexposed": reused, "new_missing_only": created,
        "external_model_calls_added": 0,
    })


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "execution.lock").open("a", encoding="utf-8") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(main())
