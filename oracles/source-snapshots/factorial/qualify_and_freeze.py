"""Qualify all references and freeze the identifiable confirmation study.

This gate runs before any scientific model request.  Geometry is recorded as a
separate evidence channel: an unavailable geometry judgement never invalidates
an otherwise identifiable event/control-flow endpoint.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from collections import Counter
from importlib.metadata import version
from pathlib import Path


P = Path(__file__).resolve().parent
QUALITY = P.parent.parent
ROOT = P.parents[3]
RUN = ROOT / "05_formal/rq2_rq4_identifiable_confirmation_v1"
BASE = P.parent / "main_study_v1"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
from runtime import execute
sys.path.insert(0, str(ROOT / "01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src"))
from geometry_interface_v01 import evaluate_dynamic_evidence


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def completed(capture: dict) -> list[dict]:
    return [event for event in capture.get("trusted_events", []) if event.get("phase") == "complete"]


def selected(events: list[dict], action: str, **args) -> list[dict]:
    return [
        event for event in events
        if event.get("action") == action
        and all(event.get("args", {}).get(key) == value for key, value in args.items())
    ]


def is_wrapper(event: dict) -> bool:
    args = event.get("args", {})
    return args.get("event_id") == "rq2_gate" or str(args.get("resource_id", "")).startswith("rq2_gap_")


def multiset(events: list[dict]) -> dict:
    return dict(sorted(Counter(event["action"] for event in events).items()))


def arm_goal_reached(spec: dict, events: list[dict], arm: str, goal: str) -> bool:
    moves = [event for event in events if event.get("action") == "move" and event.get("args", {}).get("arm") == arm]
    return moves[-1].get("args", {}).get("pose") == goal if moves else spec["pair_constants"]["initial"].get(arm) == goal


def final_goal_ok(spec: dict, events: list[dict]) -> bool:
    if not events:
        return False
    scene = events[-1].get("scene_state", {})
    for key, value in spec["pair_constants"]["goals"].items():
        if key in {"LEFT", "RIGHT"}:
            if not arm_goal_reached(spec, events, key, value):
                return False
        elif scene.get("objects", {}).get(key) != value:
            return False
    return True


def static_focal_check(task: dict, source: str, graph: dict) -> dict:
    if task["block"] == "RQ2_FACTORIAL":
        concurrent = "await asyncio.gather(_rq2_producer(), _rq2_consumer())" in source
        serial = "await _rq2_producer()\n    await _rq2_consumer()" in source
        mission_in_consumer = "        await _rq2_mission()\n    async def" not in source and "        await _rq2_mission()\n        robot.clear_event" in source
        mission_after_protocol = source.rstrip().endswith("await _rq2_mission()")
        spacing_in_consumer = "    async def _rq2_consumer():\n        await _rq2_spacing()" in source
        spacing_before_protocol = "    await _rq2_spacing()\n    await _rq2_producer()" in source or "    await _rq2_spacing()\n    await asyncio.gather(_rq2_producer(), _rq2_consumer())" in source
        checks = {
            "schedule": concurrent if task["schedule"] == "CONCURRENT" else serial,
            "coupling": mission_in_consumer if task["coupling"] == "BOUND" else mission_after_protocol,
            "distance": spacing_in_consumer if task["dependency_distance"] == "LONG" else spacing_before_protocol,
        }
    else:
        development_shape = (
            "    for _round in range(1):\n"
            "        if _round == 0:\n"
            "            await asyncio.gather(_rq2_producer(), _rq2_consumer())"
        ) in source
        ood_shape = (
            "        if receipt.version > 0:\n"
            "            await _rq2_mission()"
        ) in source and (
            "    for _round in range(1):\n"
            "        await asyncio.gather(_rq2_producer(), _rq2_consumer())"
        ) in source
        checks = {
            "finite_loop_contains_or_reaches_join": bool(graph["loop_calls_gather_interprocedural"]),
            "operator_counts": graph["for_nodes"] >= 1 and graph["if_nodes"] >= 1 and graph["gather_nodes"] >= 1,
            # Inspect the dedicated wrapper, not the inherited mission: some
            # base families legitimately contain their own IF/JOIN relation.
            "dedicated_wrapper_shape": development_shape if task["structural_split"] == "DEVELOPMENT_SHAPE" else ood_shape,
        }
    return {"passed": all(checks.values()), "checks": checks}


def dynamic_focal_check(task: dict, capture: dict) -> dict:
    events = completed(capture)
    signals = selected(events, "signal", event_id="rq2_gate")
    waits = selected(events, "wait_event", event_id="rq2_gate")
    clears = selected(events, "clear_event", event_id="rq2_gate")
    mission = [event for event in events if not is_wrapper(event) and event.get("action") != "run_return"]
    checks = {
        "exact_gate_lifecycle": len(signals) == len(waits) == len(clears) == 1,
        "mission_reached": bool(mission),
    }
    if checks["exact_gate_lifecycle"]:
        signal_i, wait_i, clear_i = signals[0]["index"], waits[0]["index"], clears[0]["index"]
        checks["signal_before_wait_before_clear"] = signal_i < wait_i < clear_i
    else:
        signal_i = wait_i = clear_i = -1
        checks["signal_before_wait_before_clear"] = False
    if task["block"] == "RQ2_FACTORIAL":
        gap_pairs = []
        for number in range(3):
            resource = f"rq2_gap_{number}"
            acquisitions = selected(events, "acquire", resource_id=resource)
            releases = selected(events, "release_resource", resource_id=resource)
            gap_pairs.append((acquisitions, releases))
        exact_gaps = all(len(a) == len(r) == 1 and a[0]["args"].get("arm") == r[0]["args"].get("arm") == "LEFT" and a[0]["index"] < r[0]["index"] for a, r in gap_pairs)
        checks["exact_gap_lifecycles"] = exact_gaps
        if exact_gaps:
            gap_indices = [event["index"] for pair in gap_pairs for events_ in pair for event in events_]
            gap_order = [pair[0][0]["index"] for pair in gap_pairs] == sorted(pair[0][0]["index"] for pair in gap_pairs)
            checks["gap_numeric_order"] = gap_order
            checks["dependency_distance"] = max(gap_indices) < signal_i if task["dependency_distance"] == "SHORT" else signal_i < min(gap_indices) and max(gap_indices) < wait_i
        else:
            checks["gap_numeric_order"] = False
            checks["dependency_distance"] = False
        if mission:
            first_mission = min(event["index"] for event in mission)
            last_mission = max(event["index"] for event in mission)
            checks["coupling_scope"] = clear_i < first_mission if task["coupling"] == "DETACHED" else wait_i < first_mission and last_mission < clear_i
        else:
            checks["coupling_scope"] = False
    elif mission:
        checks["ood_scope"] = signal_i < wait_i < min(event["index"] for event in mission) and max(event["index"] for event in mission) < clear_i
    else:
        checks["ood_scope"] = False
    final_scene = events[-1].get("scene_state", {}) if events else {}
    checks["wrapper_clean_at_return"] = (
        "rq2_gate" not in final_scene.get("active_events", {})
        and not any(str(key).startswith("rq2_gap_") for key in final_scene.get("resource_owners", {}))
        and all(final_scene.get("resource_modes", {}).get(f"rq2_gap_{number}", "OFF") == "OFF" for number in range(3))
    )
    return {"passed": all(checks.values()), "checks": checks}


async def main() -> None:
    if (P / "SCIENTIFIC_FREEZE.json").exists():
        raise RuntimeError("Scientific freeze already exists")
    pre = read(P / "PRE_REFERENCE_FREEZE.json")
    assert pre["status"] == "FROZEN_AWAITING_REFERENCE_QUALIFICATION"
    for item in pre["files"]:
        path = ROOT / item["path"]
        assert sha(path) == item["sha256"], f"Pre-reference input changed: {path}"
    base_qualification = {row["task_id"]: row for row in read(BASE / "REFERENCE_QUALIFICATION.json")["rows"]}
    tasks = read(P / "TASK_CATALOG.json")
    rows = []
    for number, task in enumerate(tasks, 1):
        directory = Path(task["spec_path"])
        directory = directory.parent
        spec = read(directory / "SPEC.json")
        source = (directory / "reference.py").read_text(encoding="utf-8")
        graph = read(directory / "GRAPH.json")
        capture = await execute(source, spec, ROOT)
        if capture.get("process", {}).get("status") == "SANDBOX_SETUP_FAILED":
            raise RuntimeError(capture.get("process", {}).get("stderr", "SANDBOX_SETUP_FAILED"))
        try:
            geometry = evaluate_dynamic_evidence(spec, capture.get("trusted_events", []), None)
        except Exception as exc:
            geometry = {"status": "GEOMETRY_EVALUATOR_ERROR", "error_type": type(exc).__name__}
        events = completed(capture)
        inherited = [event for event in events if not is_wrapper(event)]
        base_capture_path = BASE / "tasks" / task["base_task_id"] / "CAPTURE.json"
        base_capture = read(base_capture_path)
        inherited_equal = multiset(inherited) == multiset(completed(base_capture))
        parent = base_qualification[task["base_task_id"]]
        static = static_focal_check(task, source, graph)
        dynamic = dynamic_focal_check(task, capture)
        process_ok = (
            bool(capture.get("execution_lifecycle_complete"))
            and capture.get("process", {}).get("status") == "EXITED"
            and capture.get("process", {}).get("returncode") == 0
        )
        event_reference_accepted = bool(
            process_ok and parent["reference_accepted"] and inherited_equal
            and final_goal_ok(spec, events) and static["passed"] and dynamic["passed"]
        )
        geometry_reference_accepted = geometry.get("status") in {
            "NO_FORBIDDEN_CONTACT_IN_DECLARED_FIXED_AABB_TRANSLATIONS", "NOT_APPLICABLE"
        }
        write(directory / "REFERENCE_CAPTURE.json", capture)
        write(directory / "REFERENCE_GEOMETRY.json", geometry)
        write(directory / "REFERENCE_STATIC_ORACLE.json", static)
        write(directory / "REFERENCE_DYNAMIC_ORACLE.json", dynamic)
        row = {
            "task_id": task["task_id"], "family": task["family"], "block": task["block"],
            "event_reference_accepted": event_reference_accepted,
            "geometry_reference_accepted": geometry_reference_accepted,
            "geometry_endpoint_available": geometry_reference_accepted,
            "process_status": capture.get("process", {}).get("status"),
            "returncode": capture.get("process", {}).get("returncode"),
            "lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
            "parent_reference_accepted": parent["reference_accepted"],
            "inherited_executed_action_multiset_equal": inherited_equal,
            "final_goal_ok": final_goal_ok(spec, events),
            "static_focal_passed": static["passed"], "dynamic_focal_passed": dynamic["passed"],
            "geometry_status": geometry.get("status"), "executed_action_multiset": multiset(events),
            "capture_sha256": sha(directory / "REFERENCE_CAPTURE.json"),
            "geometry_sha256": sha(directory / "REFERENCE_GEOMETRY.json"),
            "static_oracle_sha256": sha(directory / "REFERENCE_STATIC_ORACLE.json"),
            "dynamic_oracle_sha256": sha(directory / "REFERENCE_DYNAMIC_ORACLE.json"),
        }
        rows.append(row)
        print(json.dumps({"n": number, "task": task["task_id"], "event_ok": event_reference_accepted, "geometry_ok": geometry_reference_accepted}, ensure_ascii=False), flush=True)
    failed = [row["task_id"] for row in rows if not row["event_reference_accepted"]]
    geometry_unavailable = [row["task_id"] for row in rows if not row["geometry_reference_accepted"]]
    by_family = {}
    for family in sorted({row["family"] for row in rows}):
        family_rows = [row for row in rows if row["family"] == family]
        factor_rows = [row for row in family_rows if row["block"] == "RQ2_FACTORIAL"]
        ood_rows = [row for row in family_rows if row["block"] == "STRUCTURAL_OOD"]
        by_family[family] = {
            "factorial_executed_action_multiset_equal_8_of_8": len({json.dumps(row["executed_action_multiset"], sort_keys=True) for row in factor_rows}) == 1,
            "ood_executed_action_multiset_equal_2_of_2": len({json.dumps(row["executed_action_multiset"], sort_keys=True) for row in ood_rows}) == 1,
        }
    mismatched = [family for family, checks in by_family.items() if not all(checks.values())]
    qualification = {
        "status": "PASS" if not failed and not mismatched else "FAIL_BEFORE_MODEL_CALLS",
        "tasks": len(rows), "event_references_accepted": len(rows) - len(failed),
        "event_reference_failures": failed, "geometry_endpoints_available": len(rows) - len(geometry_unavailable),
        "geometry_endpoints_unavailable": geometry_unavailable,
        "geometry_policy": "Recorded separately; U geometry never blocks an identifiable event/control-flow endpoint.",
        "family_matching": by_family, "family_matching_failures": mismatched,
        "new_model_calls": 0, "new_human_labels": 0, "rows": rows,
        "qualification_runtime": {"python": sys.executable, "pybullet": version("pybullet")},
    }
    write(P / "REFERENCE_QUALIFICATION.json", qualification)
    if failed or mismatched:
        write(RUN / "STATUS.json", {"phase": "REFERENCE_GATE_FAILED_BEFORE_MODEL_CALLS", "failed": failed, "mismatched": mismatched})
        raise RuntimeError("Reference qualification failed before model calls")
    freeze_files = [
        P / "PROTOCOL.md", P / "build_study.py", P / "qualify_and_freeze.py", P / "TASK_CATALOG.json",
        P / "MATCHING_AUDIT.json", P / "MODEL_PROFILES.json", P / "GENERATION_MANIFEST.json",
        P / "ANALYSIS_PLAN.json", P / "SAMPLE_SIZE_AND_STOP.json", P / "ERROR_AND_EXPOSURE_SCHEMA.json",
        P / "CHANNEL_PROBES.json", P / "PRE_REFERENCE_FREEZE.json", P / "REFERENCE_QUALIFICATION.json",
    ]
    for task in tasks:
        directory = Path(task["spec_path"]).parent
        freeze_files.extend(directory / name for name in [
            "SPEC.json", "reference.py", "GRAPH.json", "REFERENCE_CAPTURE.json", "REFERENCE_GEOMETRY.json",
            "REFERENCE_STATIC_ORACLE.json", "REFERENCE_DYNAMIC_ORACLE.json",
        ])
    write(P / "SCIENTIFIC_FREEZE.json", {
        "status": "FROZEN_READY_FOR_CAPABILITY_AND_NATURAL_COLLECTION",
        "freeze_before_scientific_model_calls": True,
        "old_runs_modified": False,
        "counts": {"families": 8, "tasks": 80, "natural_programs": 320},
        "files": [{"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size} for path in sorted(freeze_files)],
    })
    write(RUN / "STATUS.json", {"phase": "FROZEN_READY_FOR_CAPABILITY_AND_NATURAL_COLLECTION", "natural_complete": 0, "natural_total": 320, "reference_tasks_accepted": 80, "human_labels": 0})
    print(json.dumps({"status": "FROZEN", "accepted_event_references": 80, "geometry_available": 80 - len(geometry_unavailable)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
