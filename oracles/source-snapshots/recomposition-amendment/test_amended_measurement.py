"""Executable measurement gate: local-goal regressions plus 9-class C/V/NE and persistent-state injections."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V4 = HERE.parent / "rq2_structure_preserving_recomposition_v4"
RUN = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4"
OUT = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"
QUALITY = V4.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
sys.path.insert(0, str(V4))
from runtime import execute
from frozen_composer import SEEDS, compose
import run_oracle_boundary_challenges as legacy_challenges
from amended_measurement import EVENT_SEMANTICS, atomic_local_cleanup, evaluate


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def early_clear_mutation(capture: dict, event_id: str, critical_action: str, critical_args: dict) -> dict:
    mutated = copy.deepcopy(capture)
    critical = next(event for event in mutated["trusted_events"]
                    if event.get("phase") == "start" and event.get("action") == critical_action
                    and all(event.get("args", {}).get(key) == value for key, value in critical_args.items()))
    critical_index = critical["index"]
    clear_event = {
        "index": critical_index - 0.5,
        "time": critical.get("time"),
        "phase": "complete",
        "action": "clear_event",
        "args": {"event_id": event_id, "expected_version": 1},
        "scene_state": copy.deepcopy(critical.get("scene_state", {})),
    }
    clear_event["scene_state"].setdefault("active_events", {}).pop(event_id, None)
    position = mutated["trusted_events"].index(critical)
    mutated["trusted_events"].insert(position, clear_event)
    for event in mutated["trusted_events"][position + 1:]:
        if event.get("index", -1) >= critical_index:
            event.get("scene_state", {}).setdefault("active_events", {}).pop(event_id, None)
    return mutated


async def execute_until(source: str, spec: dict, policy: str, expected: str) -> tuple[dict, dict]:
    last = None
    for seed in SEEDS:
        capture = await execute(compose(source, "CONCURRENT", "SHORT", seed, policy), spec, ROOT)
        endpoint = evaluate(capture, spec)
        last = (capture, endpoint)
        if endpoint["P"] == expected:
            return last
    return last


async def main() -> None:
    catalog = {row["family_id"]: row for row in read(V4 / "REFERENCE_TASK_CATALOG.json")}
    rows = []

    # Generic local-goal regression: F14-A must not be charged with B's replacement goal.
    f14_spec = read(V4 / "reference_tasks/R2V4-F14/SPEC.json")
    f14_capture = read(RUN / "atomic_qualification/R2V4-F14--glm5--R1/A/CAPTURE.json")
    good = atomic_local_cleanup(f14_capture, f14_spec, "A")
    bad_capture = copy.deepcopy(f14_capture)
    bad_capture["trusted_events"][-1]["scene_state"]["objects"]["dropped_part"] = "recovered_bin"
    bad = atomic_local_cleanup(bad_capture, f14_spec, "A")
    rows.extend([
        {"test": "F14_A_CORRECT_LOCAL_GOAL", "expected": True, "actual": good["passed"], "passed": good["passed"] is True},
        {"test": "F14_A_OWN_QUARANTINED_OBJECT_WRONG", "expected": False, "actual": bad["passed"], "passed": bad["passed"] is False},
    ])

    representatives = legacy_challenges.REPRESENTATIVES
    safe_captures = {}
    for kind, family_id in representatives.items():
        task = catalog[family_id]
        spec = read(V4 / task["spec_path"])
        source = (V4 / task["reference_source_path"]).read_text(encoding="utf-8")
        violation_source, ne_source = legacy_challenges.variants(kind, source)
        for label, candidate in (("C", source), ("V", violation_source), ("NE", ne_source)):
            capture, endpoint = await execute_until(candidate, spec, task["serial_policy"], label)
            rows.append({
                "test": f"{kind}_{label}", "family_id": family_id,
                "expected": label, "actual": endpoint["P"],
                "exposed": endpoint["exposed"], "passed": endpoint["P"] == label,
            })
            if label == "C":
                safe_captures[kind] = (capture, spec)

    early_clear_kinds = [
        "POSE_SUPPORT_DURING_ACTION",
        "CLEARANCE_BEFORE_ACTION",
        "RELEASE_BEFORE_COMMIT",
        "HOLD_ACK_BEFORE_RELEASE",
    ]
    for kind in early_clear_kinds:
        capture, spec = safe_captures[kind]
        rule = EVENT_SEMANTICS[spec["family_id"]]["persistent_active_states"][0]
        mutated = early_clear_mutation(
            capture, rule["event_id"], rule["critical_action"], rule["critical_args"]
        )
        endpoint = evaluate(mutated, spec)
        rows.append({
            "test": f"{kind}_SIGNAL_CLEAR_BEFORE_USE",
            "expected": "V", "actual": endpoint["P"],
            "exposed": endpoint["exposed"], "passed": endpoint["P"] == "V" and endpoint["exposed"] is True,
        })

    result = {
        "schema": "paper3.rq2.v4_amendment.measurement_gate.v1",
        "status": "PASS" if all(row["passed"] for row in rows) and len(rows) == 33 else "FAIL",
        "tests": len(rows),
        "oracle_classes": len(representatives),
        "C_V_NE_per_oracle": True,
        "persistent_early_clear_cases": len(early_clear_kinds),
        "rows": rows,
        "external_model_calls_added": 0,
    }
    write_json(OUT / "MEASUREMENT_GATE.json", result)
    print(json.dumps({
        "status": result["status"], "tests": result["tests"],
        "failures": [row for row in rows if not row["passed"]],
        "external_model_calls_added": 0,
    }, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
