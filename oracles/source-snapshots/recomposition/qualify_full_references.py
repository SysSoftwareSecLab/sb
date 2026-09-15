"""Run the complete 24-family, four-condition, 16-seed reference gate."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QUALITY = HERE.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
from runtime import execute

from direct_p_oracle import evaluate, schedule_hash
from frozen_composer import SEEDS, audit_four_conditions, compose, robot_call_multiset


def read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def final_scene(capture: dict) -> dict:
    events = capture.get("trusted_events", [])
    return events[-1].get("scene_state", {}) if events else {}


def cleanup_ok(capture: dict, spec: dict) -> bool:
    scene = final_scene(capture)
    object_goals = {key: value for key, value in spec["pair_constants"]["goals"].items() if key not in {"LEFT", "RIGHT"}}
    return (
        scene.get("gripper_xyz_m", {}).get("LEFT") == spec["world"]["pose_coordinates_m"]["left_home"]
        and scene.get("gripper_xyz_m", {}).get("RIGHT") == spec["world"]["pose_coordinates_m"]["right_home"]
        and not scene.get("resource_owners", {})
        and not scene.get("active_events", {})
        and all(scene.get("objects", {}).get(object_id) == destination for object_id, destination in object_goals.items())
    )


def completed_action_multiset(capture: dict) -> dict:
    return dict(
        sorted(
            Counter(
                event["action"]
                for event in capture.get("trusted_events", [])
                if event.get("phase") == "complete" and event.get("action") != "run_return"
            ).items()
        )
    )


async def main() -> None:
    if (HERE / "SCIENTIFIC_FREEZE.json").exists():
        raise RuntimeError("scientific freeze exists; qualification cannot be rerun")
    catalog = read(HERE / "REFERENCE_TASK_CATALOG.json")
    rows = []
    family_summaries = []
    for family_number, task in enumerate(catalog, 1):
        spec_path = HERE / task["spec_path"]
        source_path = HERE / task["reference_source_path"]
        spec = read(spec_path)
        atoms = source_path.read_text(encoding="utf-8")
        static_audit = audit_four_conditions(atoms, 0, task["serial_policy"])
        family_rows = []
        for schedule in ("SERIAL", "CONCURRENT"):
            for distance in ("SHORT", "LONG"):
                for seed in SEEDS:
                    composed = compose(atoms, schedule, distance, seed, task["serial_policy"])
                    capture = await execute(composed, spec, ROOT)
                    endpoint = evaluate(capture, spec)
                    row = {
                        "family_id": task["family_id"],
                        "mechanism": task["mechanism"],
                        "schedule": schedule,
                        "distance": distance,
                        "seed": seed,
                        "lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
                        "process_status": capture.get("process", {}).get("status"),
                        "returncode": capture.get("process", {}).get("returncode"),
                        "api_error_count": len(capture.get("trusted_api_errors", [])),
                        "cleanup_ok": cleanup_ok(capture, spec),
                        "P": endpoint["P"],
                        "P_exposed": endpoint["exposed"],
                        "schedule_hash": schedule_hash(capture),
                        "completed_action_multiset": completed_action_multiset(capture),
                    }
                    rows.append(row)
                    family_rows.append(row)
        condition_multisets = defaultdict(set)
        for row in family_rows:
            key = (row["schedule"], row["distance"])
            condition_multisets[key].add(tuple(row["completed_action_multiset"].items()))
        across_condition_multisets = {
            next(iter(values)) for values in condition_multisets.values() if len(values) == 1
        }
        concurrent_hashes = {
            row["schedule_hash"] for row in family_rows if row["schedule"] == "CONCURRENT"
        }
        failures = [
            row
            for row in family_rows
            if not (
                row["lifecycle_complete"]
                and row["process_status"] == "EXITED"
                and row["returncode"] == 0
                and row["api_error_count"] == 0
                and row["cleanup_ok"]
                and row["P_exposed"]
                and row["P"] == "C"
            )
        ]
        summary = {
            "family_id": task["family_id"],
            "mechanism": task["mechanism"],
            "executions": len(family_rows),
            "accepted_executions": len(family_rows) - len(failures),
            "static_composer_audit_passed": static_audit["passed"],
            "one_action_multiset_per_condition": all(len(values) == 1 for values in condition_multisets.values()),
            "action_multiset_equal_across_four_conditions": len(across_condition_multisets) == 1,
            "concurrent_distinct_schedule_hashes": len(concurrent_hashes),
            "failed_execution_count": len(failures),
            "spec_sha256": sha(spec_path),
            "reference_source_sha256": sha(source_path),
            "prompt_sha256": sha(HERE / task["prompt_path"]),
        }
        summary["passed"] = (
            not failures
            and summary["static_composer_audit_passed"]
            and summary["one_action_multiset_per_condition"]
            and summary["action_multiset_equal_across_four_conditions"]
            and summary["concurrent_distinct_schedule_hashes"] >= 2
        )
        family_summaries.append(summary)
        print(
            json.dumps(
                {
                    "n": family_number,
                    "family_id": task["family_id"],
                    "passed": summary["passed"],
                    "accepted": summary["accepted_executions"],
                    "concurrent_hashes": summary["concurrent_distinct_schedule_hashes"],
                }
            ),
            flush=True,
        )

    failed_families = [row["family_id"] for row in family_summaries if not row["passed"]]
    result = {
        "schema": "paper3.rq2.structure_preserving_recomposition.full_reference_qualification.v1",
        "status": "PASS" if not failed_families else "FAIL_BEFORE_MODEL_CALLS",
        "families": len(family_summaries),
        "executions": len(rows),
        "accepted_executions": sum(row["accepted_executions"] for row in family_summaries),
        "failed_families": failed_families,
        "external_model_calls": 0,
        "human_review_packages": 0,
        "family_summaries": family_summaries,
    }
    write_json(HERE / "FULL_REFERENCE_QUALIFICATION.json", result)
    write_json(HERE / "FULL_REFERENCE_QUALIFICATION_ROWS.json", rows)
    print(json.dumps({"final_status": result["status"], "families": result["families"], "executions": result["executions"], "failed_families": failed_families}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
