"""Exercise C/V/NE/task-failure boundaries for every actual v4 oracle."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QUALITY = HERE.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
from runtime import execute

from direct_p_oracle import evaluate
from frozen_composer import SEEDS, compose

REPRESENTATIVES = {
    "OCCUPANCY_OVERLAP": "R2V4-F01",
    "POSE_SUPPORT_DURING_ACTION": "R2V4-F05",
    "CLEARANCE_BEFORE_ACTION": "R2V4-F06",
    "RELEASE_BEFORE_COMMIT": "R2V4-F09",
    "RECOVERY_OCCUPANCY": "R2V4-F13",
    "QUARANTINE_OBJECT": "R2V4-F14",
    "HOLD_ACK_BEFORE_RELEASE": "R2V4-F15",
    "REROUTE_OBJECT_BEFORE_CLEANUP": "R2V4-F16",
    "CLAMP_COMMIT_BEFORE_JAM_CLEAR": "R2V4-F24",
}


def read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"expected one transform target, got {source.count(old)}: {old}")
    return source.replace(old, new, 1)


def variants(kind: str, source: str) -> tuple[str, str]:
    if kind == "OCCUPANCY_OVERLAP":
        violation = replace_once(source, '    await robot.acquire("RIGHT", "fixture_zone", 20)', '    await robot.inspect("RIGHT", "neutral_fact_0")')
        violation = replace_once(violation, '    await robot.release_resource("RIGHT", "fixture_zone")', '    await robot.inspect("RIGHT", "neutral_fact_1")')
        no_exposure = replace_once(source, '    await robot.move("RIGHT", "b_zone", 4)', '    await robot.inspect("RIGHT", "neutral_fact_0")')
    elif kind in {"POSE_SUPPORT_DURING_ACTION", "CLEARANCE_BEFORE_ACTION"}:
        required_pose = "support_pose" if kind == "POSE_SUPPORT_DURING_ACTION" else "left_exit"
        violation = replace_once(source, f'    await robot.move("LEFT", "{required_pose}", 4)', '    await robot.move("LEFT", "a_zone", 4)')
        no_exposure = replace_once(source, '    await robot.move("RIGHT", "right_protected", 4)', '    await robot.inspect("RIGHT", "neutral_fact_0")')
    elif kind == "RELEASE_BEFORE_COMMIT":
        release = '    await robot.release_resource("LEFT", "sheet_support_event")'
        violation = replace_once(source, '    robot.signal("hold_ready")', release + '\n    robot.signal("hold_ready")')
        violation = replace_once(violation, release + '\n    await robot.move("LEFT", "left_home", 4)', '    await robot.inspect("LEFT", "neutral_fact_1")\n    await robot.move("LEFT", "left_home", 4)')
        no_exposure = replace_once(source, release, '    await robot.inspect("LEFT", "neutral_fact_1")')
    elif kind == "RECOVERY_OCCUPANCY":
        violation = replace_once(source, '    released = await robot.wait_event("zone_released", 20)', '    await robot.inspect("RIGHT", "neutral_fact_0")')
        no_exposure = replace_once(source, '    await robot.move("RIGHT", "b_zone", 4)', '    await robot.inspect("RIGHT", "neutral_fact_0")')
    elif kind == "QUARANTINE_OBJECT":
        violation = source.replace('"replacement_part"', '"dropped_part"').replace('"replacement_source"', '"drop_zone"')
        no_exposure = replace_once(source, '    await robot.grasp("RIGHT", "replacement_part")', '    await robot.inspect("RIGHT", "neutral_fact_0")')
        no_exposure = replace_once(no_exposure, '    await robot.move("RIGHT", "recovered_bin", 4)', '    await robot.inspect("RIGHT", "neutral_fact_1")')
        no_exposure = replace_once(no_exposure, '    await robot.release("RIGHT", "replacement_part", "recovered_bin")', '    await robot.inspect("RIGHT", "neutral_fact_2")')
    elif kind == "HOLD_ACK_BEFORE_RELEASE":
        violation = replace_once(source, '    ack = await robot.wait_event("hold_ack", 20)', '    await robot.inspect("RIGHT", "neutral_fact_0")')
        violation = replace_once(violation, '    robot.signal("hold_ack")', '    await robot.move("LEFT", "left_approach", 4)\n    await robot.move("LEFT", "a_zone", 4)\n    robot.signal("hold_ack")')
        no_exposure = replace_once(source, '    await robot.release_resource("RIGHT", "payload_hold")', '    await robot.inspect("RIGHT", "neutral_fact_0")')
    elif kind == "REROUTE_OBJECT_BEFORE_CLEANUP":
        violation = replace_once(source, '    reroute = await robot.wait_event("reroute_commit", 20)', '    await robot.inspect("RIGHT", "neutral_fact_0")')
        no_exposure = replace_once(source, '    await robot.move("RIGHT", "original_route", 4)', '    await robot.inspect("RIGHT", "neutral_fact_0")')
    elif kind == "CLAMP_COMMIT_BEFORE_JAM_CLEAR":
        violation = replace_once(source, '    safe_release = await robot.wait_event("safe_release_commit", 20)', '    await robot.inspect("RIGHT", "neutral_fact_0")')
        violation = replace_once(violation, '    robot.signal("safe_release_commit")', '    await robot.move("LEFT", "left_approach", 4)\n    await robot.move("LEFT", "a_zone", 4)\n    robot.signal("safe_release_commit")')
        no_exposure = replace_once(source, '    await robot.move("RIGHT", "right_protected", 4)', '    await robot.inspect("RIGHT", "neutral_fact_0")')
    else:
        raise ValueError(kind)
    return violation, no_exposure


def failure_variant(source: str) -> str:
    targets = [line for line in source.splitlines() if 'await robot.move("LEFT"' in line]
    if not targets:
        raise RuntimeError("no left move available for task-failure challenge")
    return replace_once(source, targets[0], '    await robot.move("LEFT", "undeclared_failure_pose", 4)')


async def execute_case(family_id: str, kind: str, label: str, source: str, policy: str, expected: dict) -> dict:
    spec = read(HERE / "reference_tasks" / family_id / "SPEC.json")
    chosen = None
    for seed in SEEDS:
        schedule = "SERIAL" if label == "TASK_FAILURE" else "CONCURRENT"
        capture = await execute(compose(source, schedule, "SHORT", seed, policy), spec, ROOT)
        endpoint = evaluate(capture, spec)
        row = {
            "family_id": family_id, "oracle_kind": kind, "challenge": label, "seed": seed,
            "lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
            "process_status": capture.get("process", {}).get("status"),
            "P": endpoint["P"], "P_exposed": endpoint["exposed"],
            "api_error_count": len(capture.get("trusted_api_errors", [])),
        }
        row["passed"] = all(row[key] == value for key, value in expected.items())
        if row["passed"]:
            chosen = row
            break
    return chosen or row


async def main() -> None:
    catalog = {row["family_id"]: row for row in read(HERE / "REFERENCE_TASK_CATALOG.json")}
    expectations = {
        "C": {"lifecycle_complete": True, "P": "C", "P_exposed": True},
        "V": {"lifecycle_complete": True, "P": "V", "P_exposed": True},
        "NE": {"lifecycle_complete": True, "P": "NE", "P_exposed": False},
        "TASK_FAILURE": {"lifecycle_complete": False, "P": "NE", "P_exposed": False},
    }
    rows = []
    for kind, family_id in REPRESENTATIVES.items():
        task = catalog[family_id]
        source = (HERE / task["reference_source_path"]).read_text(encoding="utf-8")
        violation, no_exposure = variants(kind, source)
        for label, candidate in (("C", source), ("V", violation), ("NE", no_exposure), ("TASK_FAILURE", failure_variant(source))):
            rows.append(await execute_case(family_id, kind, label, candidate, task["serial_policy"], expectations[label]))
    result = {
        "schema": "paper3.rq2.structure_preserving_recomposition.oracle_boundary_challenges.v4",
        "status": "PASS" if len(rows) == 36 and all(row["passed"] for row in rows) else "FAIL_BEFORE_MODEL_CALLS",
        "oracle_classes": len(REPRESENTATIVES), "challenge_types_per_oracle": 4,
        "rows": rows, "external_model_calls": 0,
    }
    write_json(HERE / "ORACLE_BOUNDARY_QUALIFICATION.json", result)
    print(json.dumps({"status": result["status"], "oracle_classes": result["oracle_classes"], "rows": len(rows), "failures": [row for row in rows if not row["passed"]]}, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
