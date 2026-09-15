"""Derive per-atom local postconditions and per-family event semantics from frozen references."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V4 = HERE.parent / "rq2_structure_preserving_recomposition_v4"
sys.path.insert(0, str(V4))
from atomic_isolation import compose_atomic_isolation


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def literal(node):
    return ast.literal_eval(node)


def object_goals_for_atom(source: str, spec: dict, atom: str) -> dict:
    goals = {key: value for key, value in spec["pair_constants"]["initial"].items() if key not in {"LEFT", "RIGHT"}}
    # Derive the goal from code that actually runs in the frozen isolation
    # fixture, not from the pair-global goal and not from every function merely
    # defined in the candidate.  This includes counterpart fixture actions
    # (e.g. F16-B's fixture safely reroutes A's rejected object) while excluding
    # the unexecuted peer atom (e.g. F14-A is not charged with B's replacement).
    isolation_source = compose_atomic_isolation(source, spec, atom)
    tree = ast.parse(isolation_source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}
    run_task = functions["run_task"]
    called = {
        call.func.id
        for call in ast.walk(run_task)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in functions
    }
    executed_functions = [run_task, *(functions[name] for name in sorted(called))]
    for function in executed_functions:
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            if not (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "robot" and call.func.attr == "release"):
                continue
            if len(call.args) >= 3:
                goals[literal(call.args[1])] = literal(call.args[2])
    return goals


def event_semantics(spec: dict) -> dict:
    contract = spec["rq2_direct_p_contract"]
    kind = contract["oracle_kind"]
    monotonic = []
    persistent = []
    if kind == "OCCUPANCY_OVERLAP":
        monotonic.extend(contract.get("required_events_before_b", []))
    elif kind == "RECOVERY_OCCUPANCY":
        monotonic.append(contract["required_release_event"])
    elif kind in {"POSE_SUPPORT_DURING_ACTION", "CLEARANCE_BEFORE_ACTION"}:
        monotonic.extend([*contract.get("b_pre_events", []), contract["commit_event"]])
        for event_id in contract["required_events"]:
            persistent.append({
                "event_id": event_id,
                "consumer_arm": "RIGHT",
                "critical_action": contract["protected_action"],
                "critical_args": contract["protected_args"],
                "critical_phases": ["start", "complete"],
                "requires_matching_wait_version": True,
            })
    elif kind == "RELEASE_BEFORE_COMMIT":
        monotonic.extend([*contract.get("required_prior_events", []), contract["commit_event"]])
        persistent.append({
            "event_id": contract["ready_event"],
            "consumer_arm": "RIGHT",
            "critical_action": "move",
            "critical_args": {"arm": "RIGHT", "pose": "right_protected"},
            "critical_phases": ["start"],
            "requires_matching_wait_version": True,
        })
    elif kind == "QUARANTINE_OBJECT":
        monotonic.append(contract["quarantine_commit_event"])
    elif kind == "HOLD_ACK_BEFORE_RELEASE":
        persistent.append({
            "event_id": contract["hold_ack_event"],
            "consumer_arm": "RIGHT",
            "critical_action": contract["release_action"],
            "critical_args": contract["release_args"],
            "critical_phases": ["start", "complete"],
            "requires_matching_wait_version": True,
        })
    elif kind == "REROUTE_OBJECT_BEFORE_CLEANUP":
        monotonic.append(contract["reroute_commit_event"])
    elif kind == "CLAMP_COMMIT_BEFORE_JAM_CLEAR":
        monotonic.append(contract["safe_release_event"])
    else:
        raise ValueError(kind)
    return {
        "oracle_kind": kind,
        "monotonic_milestones": sorted(set(monotonic)),
        "persistent_active_states": persistent,
    }


def main() -> None:
    catalog = read(V4 / "REFERENCE_TASK_CATALOG.json")
    local_rows = []
    event_rows = []
    for task in catalog:
        spec = read(V4 / task["spec_path"])
        source = (V4 / task["reference_source_path"]).read_text(encoding="utf-8")
        local_rows.append({
            "family_id": task["family_id"],
            "atom_A": {
                "arm_goals": {"LEFT": "left_home", "RIGHT": "right_home"},
                "object_goals": object_goals_for_atom(source, spec, "A"),
                "resource_owners": {},
                "active_events": {},
                "held": {"LEFT": None, "RIGHT": None},
                "stopped_arms": [],
                "active_failure": None,
            },
            "atom_B": {
                "arm_goals": {"LEFT": "left_home", "RIGHT": "right_home"},
                "object_goals": object_goals_for_atom(source, spec, "B"),
                "resource_owners": {},
                "active_events": {},
                "held": {"LEFT": None, "RIGHT": None},
                "stopped_arms": [],
                "active_failure": None,
            },
            "derivation": "frozen initial object states plus releases actually executed by the tested reference atom and its frozen isolation counterpart fixture; unexecuted peer-atom goals and pair-global goals are forbidden",
        })
        event_rows.append({"family_id": task["family_id"], **event_semantics(spec)})
    assert len(local_rows) == len(event_rows) == 24
    write_json(HERE / "ATOMIC_LOCAL_GOALS.json", {
        "schema": "paper3.rq2.v4_amendment.atomic_local_goals.v1",
        "families": local_rows,
    })
    write_json(HERE / "EVENT_SEMANTICS.json", {
        "schema": "paper3.rq2.v4_amendment.event_semantics.v1",
        "families": event_rows,
    })
    print(json.dumps({"families": 24, "atomic_contracts": 48, "event_semantics": 24}, indent=2))


if __name__ == "__main__":
    main()
