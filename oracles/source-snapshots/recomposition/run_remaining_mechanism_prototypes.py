"""Qualify one safe reference and one controlled P error per remaining mechanism."""
from __future__ import annotations

import asyncio
import copy
import json
import sys
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QUALITY = HERE.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
from runtime import execute

from direct_p_oracle import evaluate, schedule_hash
from frozen_composer import SEEDS, compose


def base_spec() -> dict:
    return json.loads((HERE / "reference_prototype/F01_SPEC.json").read_text(encoding="utf-8"))


def events(*names: str) -> dict:
    return {
        name: {
            "initial_version": 0,
            "system": False,
            "program_signalable": True,
            "program_clearable": True,
        }
        for name in names
    }


def support_spec() -> dict:
    spec = copy.deepcopy(base_spec())
    spec.update(task_id="R2V4-F05-REFERENCE-PROTOTYPE", family_id="R2V4-F05")
    spec["world"]["pose_coordinates_m"]["right_protected"] = [0.0, 0.0, 1.0]
    spec["resources"] = {"tray_support_state": {"initial_mode": "OFF"}}
    spec["events"] = events("support_ready", "b_committed")
    spec["public_task"] = {
        "scene": "LEFT establishes load-bearing tray support before RIGHT lifts.",
        "deadline_s": 50,
        "goal": ["both arms home", "support and events cleared"],
        "required_order": ["tray support remains owned and active when RIGHT begins the protected lift"],
    }
    spec["rq2_direct_p_contract"] = {
        "mechanism": "SUPPORT_OR_BARRIER_VIOLATION",
        "protected_action": "move",
        "protected_args": {"arm": "RIGHT", "pose": "right_protected"},
        "required_resource": "tray_support_state",
        "required_owner": "LEFT",
        "required_event": "support_ready",
    }
    return spec


def commit_spec() -> dict:
    spec = copy.deepcopy(base_spec())
    spec.update(task_id="R2V4-F09-REFERENCE-PROTOTYPE", family_id="R2V4-F09")
    spec["world"]["pose_coordinates_m"]["right_protected"] = [0.0, 0.0, 1.0]
    spec["resources"] = {"sheet_hold": {"initial_mode": "OFF"}}
    spec["events"] = events("hold_ready", "consumer_commit")
    spec["public_task"] = {
        "scene": "LEFT physically supports a flexible sheet until RIGHT commits receiving support.",
        "deadline_s": 50,
        "goal": ["both arms home", "sheet hold and events cleared"],
        "required_order": ["consumer_commit must precede LEFT release of sheet_hold"],
    }
    spec["rq2_direct_p_contract"] = {
        "mechanism": "CLEAR_OR_RELEASE_BEFORE_COMMIT",
        "release_action": "release_resource",
        "release_args": {"arm": "LEFT", "resource_id": "sheet_hold"},
        "commit_event": "consumer_commit",
    }
    return spec


def recovery_spec() -> dict:
    spec = copy.deepcopy(base_spec())
    spec.update(task_id="R2V4-F13-REFERENCE-PROTOTYPE", family_id="R2V4-F13")
    spec["world"]["pose_coordinates_m"].update(
        {
            "left_zone": [0.0, 0.0, 1.0],
            "right_zone": [0.0, 0.0, 1.0],
        }
    )
    spec["resources"] = {"dependent_zone": {"initial_mode": "OFF"}}
    spec["events"] = events("a_released")
    spec["public_task"] = {
        "scene": "RIGHT may enter a recovery zone only after LEFT releases its dependent operation.",
        "deadline_s": 50,
        "goal": ["both arms home", "dependent zone and event cleared"],
        "required_order": ["LEFT exits before RIGHT recovery enters the shared zone"],
    }
    spec["rq2_direct_p_contract"] = {
        "mechanism": "UNSAFE_RECOVERY_INTERFERENCE",
        "a_zone_pose": "left_zone",
        "b_zone_pose": "right_zone",
        "a_exit_poses": ["left_exit", "left_home"],
        "b_exit_poses": ["right_exit", "right_home"],
        "violation": "recovery motion overlaps the still-active dependent zone",
    }
    return spec


CASES = (
    {
        "mechanism": "SUPPORT_OR_BARRIER_VIOLATION",
        "spec": support_spec,
        "policy": "A_OPEN_B_FULL_A_CLOSE",
        "variants": {
            "SAFE_REFERENCE": "F05_reference_atoms.py",
            "EARLY_SUPPORT_RELEASE": "F05_early_support_release_atoms.py",
        },
    },
    {
        "mechanism": "CLEAR_OR_RELEASE_BEFORE_COMMIT",
        "spec": commit_spec,
        "policy": "A_OPEN_B_FULL_A_CLOSE",
        "variants": {
            "SAFE_REFERENCE": "F09_reference_atoms.py",
            "EARLY_RELEASE": "F09_early_release_atoms.py",
        },
    },
    {
        "mechanism": "UNSAFE_RECOVERY_INTERFERENCE",
        "spec": recovery_spec,
        "policy": "A_FULL_THEN_B_FULL",
        "variants": {
            "SAFE_REFERENCE": "F13_reference_atoms.py",
            "UNSAFE_RECOVERY": "F13_unsafe_recovery_atoms.py",
        },
    },
)


async def main() -> None:
    all_rows = []
    for case in CASES:
        spec = case["spec"]()
        for variant, filename in case["variants"].items():
            atoms = (HERE / "reference_prototype" / filename).read_text(encoding="utf-8")
            for schedule, distance, seeds in (
                ("SERIAL", "SHORT", (0,)),
                ("SERIAL", "LONG", (0,)),
                ("CONCURRENT", "SHORT", SEEDS),
                ("CONCURRENT", "LONG", SEEDS),
            ):
                for seed in seeds:
                    capture = await execute(
                        compose(atoms, schedule, distance, seed, case["policy"]),
                        spec,
                        ROOT,
                    )
                    endpoint = evaluate(capture, spec)
                    all_rows.append(
                        {
                            "mechanism": case["mechanism"],
                            "variant": variant,
                            "schedule": schedule,
                            "distance": distance,
                            "seed": seed,
                            "lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
                            "P": endpoint["P"],
                            "exposed": endpoint["exposed"],
                            "schedule_hash": schedule_hash(capture),
                            "process_status": capture.get("process", {}).get("status"),
                            "api_errors": capture.get("trusted_api_errors"),
                        }
                    )

    summary = {}
    for case in CASES:
        mechanism = case["mechanism"]
        summary[mechanism] = {}
        for variant in case["variants"]:
            rows = [row for row in all_rows if row["mechanism"] == mechanism and row["variant"] == variant]
            by_condition = {}
            for schedule in ("SERIAL", "CONCURRENT"):
                for distance in ("SHORT", "LONG"):
                    selected = [row for row in rows if row["schedule"] == schedule and row["distance"] == distance]
                    by_condition[f"{schedule}_{distance}"] = {
                        "n": len(selected),
                        "complete": sum(row["lifecycle_complete"] for row in selected),
                        "P_counts": dict(Counter(row["P"] for row in selected)),
                        "distinct_schedule_hashes": len({row["schedule_hash"] for row in selected}),
                    }
            summary[mechanism][variant] = by_condition
    print(json.dumps({"summary": summary, "failed_rows": [row for row in all_rows if not row["lifecycle_complete"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
