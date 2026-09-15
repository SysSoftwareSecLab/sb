"""Post-generation condition-blind qualification and fixed factorial execution."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QUALITY = HERE.parent.parent
RUN = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
from runtime import execute

from atomic_contract_oracle import dynamic_local_contract, static_local_contract
from atomic_isolation import compose_atomic_isolation
from direct_p_oracle import evaluate, schedule_hash
from frozen_composer import SEEDS, audit_four_conditions, compose


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def verify_freeze() -> dict:
    freeze = read(HERE / "SCIENTIFIC_FREEZE.json")
    if freeze["status"] != "FROZEN_FOR_FINITE_EXECUTION":
        raise RuntimeError("SCIENTIFIC_FREEZE_NOT_ACTIVE")
    for item in freeze["files"]:
        if sha(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError("FROZEN_FILE_CHANGED:" + item["path"])
    return freeze


def final_scene(capture: dict) -> dict:
    events = capture.get("trusted_events", [])
    return events[-1].get("scene_state", {}) if events else {}


def cleanup_ok(capture: dict, spec: dict) -> bool:
    scene = final_scene(capture)
    object_goals = {
        key: value
        for key, value in spec["pair_constants"]["goals"].items()
        if key not in {"LEFT", "RIGHT"}
    }
    return (
        scene.get("gripper_xyz_m", {}).get("LEFT") == spec["world"]["pose_coordinates_m"]["left_home"]
        and scene.get("gripper_xyz_m", {}).get("RIGHT") == spec["world"]["pose_coordinates_m"]["right_home"]
        and not scene.get("resource_owners", {})
        and not scene.get("active_events", {})
        and all(scene.get("objects", {}).get(object_id) == destination for object_id, destination in object_goals.items())
    )


def completed_action_multiset(capture: dict) -> dict:
    return dict(sorted(Counter(
        event["action"]
        for event in capture.get("trusted_events", [])
        if event.get("phase") == "complete" and event.get("action") != "run_return"
    ).items()))


async def qualify_slot(slot: dict, spec: dict) -> dict:
    folder = RUN / "generation" / slot["slot_id"]
    result = read(folder / "RESULT.json")
    summary = {
        "slot_id": slot["slot_id"],
        "family_id": slot["family_id"],
        "mechanism": slot["mechanism"],
        "profile": slot["profile"],
        "repeat": slot["repeat"],
        "generation_status": result["status"],
        "interface_valid": bool(result.get("interface_valid")),
        "atoms": [],
    }
    candidate_path = folder / "candidate.py"
    if not result.get("interface_valid") or not candidate_path.exists():
        summary.update(static_contract_ok=False, static_contract_errors=["NO_VALID_ATOMIC_SOURCE"], eligible=False)
        return summary
    if result.get("source_sha256") != sha(candidate_path):
        raise RuntimeError("CANDIDATE_SOURCE_CHANGED:" + slot["slot_id"])
    source = candidate_path.read_text(encoding="utf-8")
    static = static_local_contract(source, spec)
    summary.update(static_contract_ok=static["passed"], static_contract_errors=static["errors"])
    if not static["passed"]:
        summary["eligible"] = False
        return summary
    for atom in ("A", "B"):
        atom_folder = RUN / "atomic_qualification" / slot["slot_id"] / atom
        row_path = atom_folder / "RESULT.json"
        capture_path = atom_folder / "CAPTURE.json"
        if not row_path.exists():
            capture = await execute(compose_atomic_isolation(source, spec, atom), spec, ROOT)
            write_json(capture_path, capture)
            local = dynamic_local_contract(capture, spec, atom)
            direct_p = evaluate(capture, spec)
            row = {
                "atom": atom,
                "lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
                "process_status": capture.get("process", {}).get("status"),
                "returncode": capture.get("process", {}).get("returncode"),
                "api_error_count": len(capture.get("trusted_api_errors", [])),
                "cleanup_ok": cleanup_ok(capture, spec),
                "dynamic_contract_ok": local["passed"],
                "dynamic_contract_reason": local["reason"],
                "direct_P": direct_p["P"],
                "capture_sha256": sha(capture_path),
            }
            row["passed"] = (
                row["lifecycle_complete"]
                and row["process_status"] == "EXITED"
                and row["returncode"] == 0
                and row["api_error_count"] == 0
                and row["cleanup_ok"]
                and row["dynamic_contract_ok"]
                and row["direct_P"] != "V"
            )
            write_json(row_path, row)
        row = read(row_path)
        if row["capture_sha256"] != sha(capture_path):
            raise RuntimeError("ATOMIC_CAPTURE_CHANGED:" + slot["slot_id"] + ":" + atom)
        summary["atoms"].append(row)
    summary["eligible"] = all(row["passed"] for row in summary["atoms"])
    return summary


def coverage_gate(rows: list[dict]) -> dict:
    eligible = [row for row in rows if row["eligible"]]
    all_families = sorted({row["family_id"] for row in rows})
    family_coverage = sorted({row["family_id"] for row in eligible})
    mechanism_coverage = {}
    for mechanism in sorted({row["mechanism"] for row in rows}):
        mechanism_coverage[mechanism] = len({row["family_id"] for row in eligible if row["mechanism"] == mechanism})
    model_family_coverage = {}
    for profile in sorted({row["profile"] for row in rows}):
        model_family_coverage[profile] = len({row["family_id"] for row in eligible if row["profile"] == profile})
    model_family_sets = {
        profile: {row["family_id"] for row in eligible if row["profile"] == profile}
        for profile in sorted({row["profile"] for row in rows})
    }
    common_model_families = set.intersection(*model_family_sets.values()) if model_family_sets else set()
    common_by_mechanism = {
        mechanism: len({row["family_id"] for row in eligible if row["mechanism"] == mechanism} & common_model_families)
        for mechanism in sorted({row["mechanism"] for row in rows})
    }
    passed = (
        len(family_coverage) == 24
        and all(value == 6 for value in mechanism_coverage.values())
        and all(value == 24 for value in model_family_coverage.values())
        and len(common_model_families) == 24
        and all(value == 6 for value in common_by_mechanism.values())
    )
    return {
        "schema": "paper3.rq2.structure_preserving_recomposition.postmodel_eligibility_gate.v1",
        "status": "PASS_CONTINUE_TO_FACTORIAL_EXECUTION" if passed else "STOP_NO_PRIMARY_CONFIRMATION_NO_HUMAN_PACKAGE",
        "passed": passed,
        "fixed_generation_slots": len(rows),
        "eligible_slots": len(eligible),
        "family_coverage": len(family_coverage),
        "required_family_coverage": 24,
        "missing_families": sorted(set(all_families) - set(family_coverage)),
        "mechanism_family_coverage": mechanism_coverage,
        "required_per_mechanism": 6,
        "model_family_coverage": model_family_coverage,
        "required_per_model": 24,
        "common_model_family_coverage": len(common_model_families),
        "required_common_model_family_coverage": 24,
        "common_model_families": sorted(common_model_families),
        "common_model_families_per_mechanism": common_by_mechanism,
        "no_resampling": True,
    }


async def execute_slot(slot: dict, spec: dict) -> list[dict]:
    source_path = RUN / "generation" / slot["slot_id"] / "candidate.py"
    source = source_path.read_text(encoding="utf-8")
    audit = audit_four_conditions(source, 0, slot["serial_policy"])
    if not audit["passed"]:
        raise RuntimeError("COMPOSER_STATIC_AUDIT_FAILED:" + slot["slot_id"])
    rows = []
    for schedule in ("SERIAL", "CONCURRENT"):
        for distance in ("SHORT", "LONG"):
            condition = schedule + "_" + distance
            for seed in SEEDS:
                folder = RUN / "factorial_execution" / slot["slot_id"] / condition / f"seed_{seed:02d}"
                row_path = folder / "RESULT.json"
                capture_path = folder / "CAPTURE.json"
                source_file = folder / "composed.py"
                if not row_path.exists():
                    composed = compose(source, schedule, distance, seed, slot["serial_policy"])
                    folder.mkdir(parents=True, exist_ok=True)
                    source_file.write_text(composed, encoding="utf-8")
                    capture = await execute(composed, spec, ROOT)
                    write_json(capture_path, capture)
                    endpoint = evaluate(capture, spec)
                    row = {
                        "slot_id": slot["slot_id"],
                        "family_id": slot["family_id"],
                        "mechanism": slot["mechanism"],
                        "profile": slot["profile"],
                        "repeat": slot["repeat"],
                        "schedule": schedule,
                        "distance": distance,
                        "condition": condition,
                        "seed": seed,
                        "lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
                        "process_status": capture.get("process", {}).get("status"),
                        "returncode": capture.get("process", {}).get("returncode"),
                        "api_error_count": len(capture.get("trusted_api_errors", [])),
                        "cleanup_ok": cleanup_ok(capture, spec),
                        "P": endpoint["P"],
                        "P_exposed": endpoint["exposed"],
                        "P_reason": endpoint["reason"],
                        "schedule_hash": schedule_hash(capture),
                        "completed_action_multiset": completed_action_multiset(capture),
                        "model_body_sha256": sha(source_path),
                        "composed_source_sha256": sha(source_file),
                        "capture_sha256": sha(capture_path),
                    }
                    write_json(row_path, row)
                row = read(row_path)
                if row["model_body_sha256"] != sha(source_path):
                    raise RuntimeError("MODEL_BODY_CHANGED:" + slot["slot_id"])
                if row["composed_source_sha256"] != sha(source_file) or row["capture_sha256"] != sha(capture_path):
                    raise RuntimeError("FACTORIAL_EVIDENCE_CHANGED:" + slot["slot_id"] + ":" + condition)
                rows.append(row)
    return rows


async def main() -> None:
    verify_freeze()
    if (RUN / "TECHNICAL_HOLD.json").exists():
        raise RuntimeError("TECHNICAL_HOLD_PRESENT")
    manifest = read(HERE / "GENERATION_MANIFEST.json")
    catalog = {row["family_id"]: row for row in read(HERE / "REFERENCE_TASK_CATALOG.json")}
    qualification_rows = []
    for index, slot in enumerate(manifest, 1):
        verify_freeze()
        spec = read(HERE / slot["spec_path"])
        row = await qualify_slot(slot, spec)
        qualification_rows.append(row)
        print(json.dumps({"phase": "atomic_qualification", "n": index, "total": len(manifest), "slot": slot["slot_id"], "eligible": row["eligible"]}), flush=True)
    write_json(RUN / "ATOMIC_QUALIFICATION_ROWS.json", qualification_rows)
    gate = coverage_gate(qualification_rows)
    write_json(RUN / "POSTMODEL_ELIGIBILITY_GATE.json", gate)
    if not gate["passed"]:
        write_json(RUN / "STATUS.json", {"phase": gate["status"], "updated_utc": now(), "external_model_calls": 96, "human_review_packages": 0})
        print(json.dumps(gate, ensure_ascii=False, indent=2))
        return
    eligible_ids = {row["slot_id"] for row in qualification_rows if row["eligible"]}
    execution_rows = []
    for index, slot in enumerate((row for row in manifest if row["slot_id"] in eligible_ids), 1):
        verify_freeze()
        spec = read(HERE / catalog[slot["family_id"]]["spec_path"])
        execution_rows.extend(await execute_slot(slot, spec))
        write_json(RUN / "EXECUTION_ROWS.partial.json", execution_rows)
        write_json(RUN / "STATUS.json", {"phase": "FACTORIAL_EXECUTION", "eligible_slot_complete": index, "eligible_slot_total": len(eligible_ids), "execution_rows": len(execution_rows), "updated_utc": now()})
        print(json.dumps({"phase": "factorial_execution", "n": index, "total": len(eligible_ids), "slot": slot["slot_id"], "rows": len(execution_rows)}), flush=True)
    write_json(RUN / "EXECUTION_ROWS.json", execution_rows)
    write_json(RUN / "STATUS.json", {"phase": "FACTORIAL_EXECUTION_COMPLETE", "eligible_slots": len(eligible_ids), "execution_rows": len(execution_rows), "updated_utc": now()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    RUN.mkdir(parents=True, exist_ok=True)
    with (RUN / "execution.lock").open("a", encoding="utf-8") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(main())
