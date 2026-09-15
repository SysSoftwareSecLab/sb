"""Correct producer-aware persistent-state scoring; amendment-001 scores stay preserved."""
from __future__ import annotations

import json
from pathlib import Path

import amended_measurement as v1


HERE = Path(__file__).resolve().parent


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


EVENT_SEMANTICS = {row["family_id"]: row for row in read(HERE / "EVENT_SEMANTICS_CORRECTION_002.json")["families"]}
schedule_hash = v1.schedule_hash
atomic_local_cleanup = v1.atomic_local_cleanup


def persistent_state_audit(capture: dict, spec: dict) -> dict:
    semantics = EVENT_SEMANTICS[spec["family_id"]]
    rows = []
    reached = True
    passed = True
    for rule in semantics["persistent_active_states"]:
        critical_events = []
        for phase in rule["critical_phases"]:
            critical_events.extend(v1._matching(capture, rule["critical_action"], rule["critical_args"], phase))
        if not critical_events:
            reached = False
            passed = False
            rows.append({"event_id": rule["event_id"], "reached": False, "passed": False, "reason": "critical use not reached"})
            continue
        for event in sorted(critical_events, key=lambda row: row.get("index", -1)):
            active = event.get("scene_state", {}).get("active_events", {}).get(rule["event_id"])
            active_version = active.get("version") if isinstance(active, dict) else None
            wait_version = v1._wait_version_before(capture, rule["event_id"], event.get("index", -1), rule["consumer_arm"])
            if rule["requires_matching_wait_version"]:
                row_passed = active_version is not None and wait_version == active_version
            else:
                row_passed = active_version is not None
            rows.append({
                "event_id": rule["event_id"], "producer_role": rule["producer_role"],
                "critical_action": rule["critical_action"], "critical_phase": event.get("phase"),
                "critical_index": event.get("index"), "active_version": active_version,
                "wait_version": wait_version, "requires_matching_wait_version": rule["requires_matching_wait_version"],
                "reached": True, "passed": row_passed,
                "reason": "persistent event active with required producer-consumer evidence" if row_passed else "persistent event absent or external wait-use version mismatch",
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
    original = v1.original_oracle.evaluate(capture, spec)
    persistent = persistent_state_audit(capture, spec)
    if not persistent["applicable"]:
        return {**original, "measurement_revision": "SCORING_CORRECTION_002", "persistent_state_audit": persistent}
    if not persistent["reached"] and original["P"] == "NE":
        return {**original, "measurement_revision": "SCORING_CORRECTION_002", "persistent_state_audit": persistent}
    if original["P"] == "C" and not persistent["passed"]:
        return {**original, "P": "V", "exposed": True,
                "reason": "persistent prerequisite absent or externally produced version not carried to dependent use",
                "measurement_revision": "SCORING_CORRECTION_002", "persistent_state_audit": persistent}
    return {**original, "measurement_revision": "SCORING_CORRECTION_002", "persistent_state_audit": persistent}
