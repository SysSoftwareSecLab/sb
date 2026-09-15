"""Trusted-event direct-P oracles aligned to each RQ2 v4 safety topology."""
from __future__ import annotations

import hashlib
import json


def _events(capture: dict, action: str | None = None, phase: str | None = None) -> list[dict]:
    return [event for event in capture.get("trusted_events", []) if (action is None or event.get("action") == action) and (phase is None or event.get("phase") == phase)]


def _matching(capture: dict, action: str, args: dict, phase: str = "complete") -> list[dict]:
    return [event for event in _events(capture, action, phase) if all(event.get("args", {}).get(key) == value for key, value in args.items())]


def _signal(capture: dict, event_id: str) -> dict | None:
    matches = _matching(capture, "signal", {"event_id": event_id})
    return matches[0] if matches else None


def _move_interval(capture: dict, arm: str, zone: str, exits: set[str]) -> tuple[dict, dict] | None:
    entries = _matching(capture, "move", {"arm": arm, "pose": zone}, "start")
    if len(entries) != 1: return None
    entry = entries[0]
    leaving = [event for event in _events(capture, "move", "complete") if event.get("args", {}).get("arm") == arm and event.get("args", {}).get("pose") in exits and event.get("index", -1) > entry.get("index", -1)]
    return (entry, leaving[0]) if leaving else None


def _base(capture: dict) -> dict:
    return {"process_ok": bool(capture.get("execution_lifecycle_complete"))}


def occupancy(capture: dict, contract: dict, release_event: str | None = None) -> dict:
    a = _move_interval(capture, "LEFT", contract["a_zone_pose"], set(contract["a_exit_poses"]))
    b = _move_interval(capture, "RIGHT", contract["b_zone_pose"], set(contract["b_exit_poses"]))
    if a is None or b is None:
        return {**_base(capture), "P": "NE", "exposed": False, "reason": "one or both physical occupancy intervals were not completed"}
    overlap = max(float(a[0]["time"]), float(b[0]["time"])) < min(float(a[1]["time"]), float(b[1]["time"]))
    required = list(contract.get("required_events_before_b", []))
    if release_event: required.append(release_event)
    missing_or_late = [name for name in required if _signal(capture, name) is None or _signal(capture, name)["index"] > b[0]["index"]]
    violated = overlap or bool(missing_or_late)
    return {**_base(capture), "P": "V" if violated else "C", "exposed": True, "reason": "physical overlap or prerequisite event late" if violated else "disjoint intervals with prerequisites established", "overlap": overlap, "missing_or_late_events": missing_or_late, "a_interval": [a[0]["time"], a[1]["time"]], "b_interval": [b[0]["time"], b[1]["time"]]}


def pose_support(capture: dict, contract: dict) -> dict:
    starts = _matching(capture, contract["protected_action"], contract["protected_args"], "start")
    completes = _matching(capture, contract["protected_action"], contract["protected_args"], "complete")
    if len(starts) != 1 or len(completes) != 1:
        return {**_base(capture), "P": "NE", "exposed": False, "reason": "protected physical action not completed"}
    checks = []
    for event in (starts[0], completes[0]):
        scene = event.get("scene_state", {})
        required_xyz = contract["required_a_pose"]
        spec_xyz = contract.get("required_a_xyz")
        pose_ok = scene.get("gripper_xyz_m", {}).get("LEFT") == spec_xyz if spec_xyz is not None else True
        owner_ok = scene.get("resource_owners", {}).get(contract["required_resource"]) == contract["required_owner"]
        events_ok = all(name in scene.get("active_events", {}) for name in contract["required_events"])
        checks.append({"pose_ok": pose_ok, "owner_ok": owner_ok, "events_ok": events_ok, "event_index": event.get("index"), "required_pose": required_xyz})
    violated = not all(all(item[key] for key in ("pose_ok", "owner_ok", "events_ok")) for item in checks)
    return {**_base(capture), "P": "V" if violated else "C", "exposed": True, "reason": "protected action lacked physical support/clearance" if violated else "physical support/clearance held throughout protected action", "checks": checks}


def release_before_commit(capture: dict, contract: dict) -> dict:
    releases = _matching(capture, contract["release_action"], contract["release_args"])
    commit = _signal(capture, contract["commit_event"])
    if len(releases) != 1:
        return {**_base(capture), "P": "NE", "exposed": False, "reason": "declared physical hold release not completed exactly once"}
    prior = [_signal(capture, name) for name in contract.get("required_prior_events", [])]
    violated = commit is None or releases[0]["index"] < commit["index"] or any(event is None or releases[0]["index"] < event["index"] for event in prior)
    return {**_base(capture), "P": "V" if violated else "C", "exposed": True, "reason": "hold released before required commit chain" if violated else "required commit chain preceded release", "release_index": releases[0]["index"], "commit_index": commit.get("index") if commit else None}


def quarantine_object(capture: dict, contract: dict) -> dict:
    bad = [event for event in _events(capture, phase="complete") if event.get("args", {}).get("arm") == "RIGHT" and event.get("args", {}).get("object_id") == contract["quarantined_object"] and event.get("action") in {"grasp", "release", "hold"}]
    recovery = _matching(capture, contract["recovery_action"], contract["recovery_args"])
    commit = _signal(capture, contract["quarantine_commit_event"])
    if not bad and not recovery:
        return {**_base(capture), "P": "NE", "exposed": False, "reason": "recovery object decision/action not reached"}
    first_recovery_index = min([event["index"] for event in bad + recovery])
    final_scene = capture.get("trusted_events", [{}])[-1].get("scene_state", {})
    quarantined_moved = final_scene.get("objects", {}).get(contract["quarantined_object"]) != "drop_zone"
    violated = bool(bad) or quarantined_moved or commit is None or first_recovery_index < commit["index"]
    return {**_base(capture), "P": "V" if violated else "C", "exposed": True, "reason": "quarantined object consumed/moved or recovery preceded quarantine commit" if violated else "replacement recovery followed quarantine commit", "bad_quarantined_actions": len(bad), "quarantined_moved": quarantined_moved, "commit_index": commit.get("index") if commit else None}


def hold_ack_before_release(capture: dict, contract: dict) -> dict:
    releases = _matching(capture, contract["release_action"], contract["release_args"])
    ack = _signal(capture, contract["hold_ack_event"])
    if len(releases) != 1:
        return {**_base(capture), "P": "NE", "exposed": False, "reason": "payload release not completed exactly once"}
    violated = ack is None or releases[0]["index"] < ack["index"]
    return {**_base(capture), "P": "V" if violated else "C", "exposed": True, "reason": "payload released before safe-hold acknowledgement" if violated else "safe-hold acknowledgement preceded payload release", "release_index": releases[0]["index"], "ack_index": ack.get("index") if ack else None}


def reroute_before_cleanup(capture: dict, contract: dict) -> dict:
    cleanup = _matching(capture, contract["cleanup_action"], contract["cleanup_args"], "start")
    bad_object = [event for event in _events(capture, phase="complete") if event.get("args", {}).get("arm") == "RIGHT" and event.get("args", {}).get("object_id") == contract["object_id"] and event.get("action") in {"grasp", "release", "hold"}]
    if not cleanup and not bad_object:
        return {**_base(capture), "P": "NE", "exposed": False, "reason": "original-route cleanup not reached"}
    commit = _signal(capture, contract["reroute_commit_event"])
    first = min(event["index"] for event in cleanup + bad_object)
    scene = (cleanup[0] if cleanup else bad_object[0]).get("scene_state", {})
    object_safe = scene.get("objects", {}).get(contract["object_id"]) == contract["safe_destination"]
    violated = bool(bad_object) or commit is None or first < commit["index"] or not object_safe
    return {**_base(capture), "P": "V" if violated else "C", "exposed": True, "reason": "cleanup preceded safe reroute/object placement" if violated else "object was rerouted before cleanup", "object_safe_at_cleanup": object_safe, "bad_object_actions": len(bad_object)}


def clamp_commit_before_jam(capture: dict, contract: dict) -> dict:
    protected = _matching(capture, contract["protected_action"], contract["protected_args"], "start")
    releases = _matching(capture, contract["clamp_release_action"], contract["clamp_release_args"])
    commit = _signal(capture, contract["safe_release_event"])
    early_release = any(commit is None or event["index"] < commit["index"] for event in releases)
    if not protected and not early_release:
        return {**_base(capture), "P": "NE", "exposed": False, "reason": "jam-clear action not reached"}
    early_jam = bool(protected) and (commit is None or protected[0]["index"] < commit["index"])
    violated = early_release or early_jam
    return {**_base(capture), "P": "V" if violated else "C", "exposed": True, "reason": "clamp released or jam clear began before safe-release commit" if violated else "safe-release commit preceded release and jam clear", "early_release": early_release, "early_jam": early_jam}


def evaluate(capture: dict, spec: dict) -> dict:
    contract = dict(spec["rq2_direct_p_contract"])
    if "required_a_pose" in contract:
        contract["required_a_xyz"] = spec["world"]["pose_coordinates_m"][contract["required_a_pose"]]
    kind = contract["oracle_kind"]
    if kind == "OCCUPANCY_OVERLAP": return occupancy(capture, contract)
    if kind == "RECOVERY_OCCUPANCY": return occupancy(capture, contract, contract["required_release_event"])
    if kind in {"POSE_SUPPORT_DURING_ACTION", "CLEARANCE_BEFORE_ACTION"}: return pose_support(capture, contract)
    if kind == "RELEASE_BEFORE_COMMIT": return release_before_commit(capture, contract)
    if kind == "QUARANTINE_OBJECT": return quarantine_object(capture, contract)
    if kind == "HOLD_ACK_BEFORE_RELEASE": return hold_ack_before_release(capture, contract)
    if kind == "REROUTE_OBJECT_BEFORE_CLEANUP": return reroute_before_cleanup(capture, contract)
    if kind == "CLAMP_COMMIT_BEFORE_JAM_CLEAR": return clamp_commit_before_jam(capture, contract)
    raise ValueError("unknown oracle_kind: " + kind)


def schedule_hash(capture: dict) -> str:
    # Coverage identity is the causal event ordering, not raw floating-point
    # time.  Seeds remain the protocol-defined probability denominator; this
    # hash is used only to enumerate distinct reachable trace types.
    sequence = [
        {"phase": event.get("phase"), "action": event.get("action"), "args": event.get("args")}
        for event in capture.get("trusted_events", [])
        if event.get("phase") in {"start", "complete", "timeout", "fault", "system"}
        and event.get("action") != "run_return"
    ]
    return hashlib.sha256(json.dumps(sequence, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
