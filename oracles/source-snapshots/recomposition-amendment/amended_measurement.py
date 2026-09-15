"""Versioned v4 measurement fixes; original v4 labels remain immutable."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
V4 = HERE.parent / "rq2_structure_preserving_recomposition_v4"
sys.path.insert(0, str(V4))
import direct_p_oracle as original_oracle


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


LOCAL_GOALS = {row["family_id"]: row for row in read(HERE / "ATOMIC_LOCAL_GOALS.json")["families"]}
EVENT_SEMANTICS = {row["family_id"]: row for row in read(HERE / "EVENT_SEMANTICS.json")["families"]}


def final_scene(capture: dict) -> dict:
    events = capture.get("trusted_events", [])
    return events[-1].get("scene_state", {}) if events else {}


def atomic_local_cleanup(capture: dict, spec: dict, atom: str) -> dict:
    family_id = spec["family_id"]
    goal = LOCAL_GOALS[family_id]["atom_" + atom]
    scene = final_scene(capture)
    pose_coordinates = spec["world"]["pose_coordinates_m"]
    checks = {
        "arm_goals": all(scene.get("gripper_xyz_m", {}).get(arm) == pose_coordinates[pose] for arm, pose in goal["arm_goals"].items()),
        "object_goals": all(scene.get("objects", {}).get(object_id) == destination for object_id, destination in goal["object_goals"].items()),
        "resource_owners": scene.get("resource_owners", {}) == goal["resource_owners"],
        "active_events": scene.get("active_events", {}) == goal["active_events"],
        "held": scene.get("held", {}) == goal["held"],
        "stopped_arms": scene.get("stopped_arms", []) == goal["stopped_arms"],
        "active_failure": scene.get("active_failure") == goal["active_failure"],
    }
    return {"passed": all(checks.values()), "checks": checks, "goal": goal}


def _matching(capture: dict, action: str, args: dict, phase: str | None = None) -> list[dict]:
    return [event for event in capture.get("trusted_events", [])
            if event.get("action") == action
            and (phase is None or event.get("phase") == phase)
            and all(event.get("args", {}).get(key) == value for key, value in args.items())]


def _wait_version_before(capture: dict, event_id: str, critical_index: float, consumer_arm: str) -> int | None:
    candidates = []
    for event in capture.get("trusted_events", []):
        if event.get("index", -1) >= critical_index or event.get("phase") != "complete" or event.get("action") != "wait_event":
            continue
        if event.get("args", {}).get("event_id") != event_id:
            continue
        # The runtime records the waiting arm only through the candidate task;
        # the event result version is the trusted identity carried to use.
        version = event.get("result", {}).get("version")
        if version is not None:
            candidates.append((event.get("index", -1), int(version)))
    return max(candidates)[1] if candidates else None


def persistent_state_audit(capture: dict, spec: dict) -> dict:
    semantics = EVENT_SEMANTICS[spec["family_id"]]
    rows = []
    reached = True
    passed = True
    for rule in semantics["persistent_active_states"]:
        critical_events = []
        for phase in rule["critical_phases"]:
            critical_events.extend(_matching(capture, rule["critical_action"], rule["critical_args"], phase))
        if not critical_events:
            reached = False
            passed = False
            rows.append({"event_id": rule["event_id"], "reached": False, "passed": False, "reason": "critical use not reached"})
            continue
        for event in sorted(critical_events, key=lambda row: row.get("index", -1)):
            active = event.get("scene_state", {}).get("active_events", {}).get(rule["event_id"])
            wait_version = _wait_version_before(capture, rule["event_id"], event.get("index", -1), rule["consumer_arm"])
            active_version = active.get("version") if isinstance(active, dict) else None
            row_passed = active_version is not None and (
                not rule["requires_matching_wait_version"] or wait_version == active_version
            )
            rows.append({
                "event_id": rule["event_id"],
                "critical_action": rule["critical_action"],
                "critical_phase": event.get("phase"),
                "critical_index": event.get("index"),
                "active_version": active_version,
                "wait_version": wait_version,
                "reached": True,
                "passed": row_passed,
                "reason": "persistent event active with matching wait version" if row_passed else "persistent event absent or wait-use version mismatch",
            })
            passed = passed and row_passed
    return {
        "applicable": bool(semantics["persistent_active_states"]),
        "reached": reached,
        "passed": passed if semantics["persistent_active_states"] else True,
        "rows": rows,
        "monotonic_milestones": semantics["monotonic_milestones"],
    }


def evaluate(capture: dict, spec: dict) -> dict:
    original = original_oracle.evaluate(capture, spec)
    persistent = persistent_state_audit(capture, spec)
    if not persistent["applicable"]:
        return {**original, "measurement_revision": "AMENDMENT_001", "persistent_state_audit": persistent}
    if not persistent["reached"] and original["P"] == "NE":
        return {**original, "measurement_revision": "AMENDMENT_001", "persistent_state_audit": persistent}
    if original["P"] == "C" and not persistent["passed"]:
        return {
            **original,
            "P": "V",
            "exposed": True,
            "reason": "persistent prerequisite was signaled but absent or version-mismatched at dependent use",
            "measurement_revision": "AMENDMENT_001",
            "persistent_state_audit": persistent,
        }
    return {**original, "measurement_revision": "AMENDMENT_001", "persistent_state_audit": persistent}


def schedule_hash(capture: dict) -> str:
    sequence = [
        {"phase": event.get("phase"), "action": event.get("action"), "args": event.get("args")}
        for event in capture.get("trusted_events", [])
        if event.get("phase") in {"start", "complete", "timeout", "fault", "system"}
        and event.get("action") != "run_return"
    ]
    return hashlib.sha256(json.dumps(sequence, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
