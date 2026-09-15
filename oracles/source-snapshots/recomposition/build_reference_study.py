"""Materialize 24 safety-topology-distinct RQ2 v4 reference tasks."""
from __future__ import annotations

from collections import defaultdict
import ast
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "reference_tasks"
HOOKS = ("atom_a_prepare", "atom_a_dependency", "atom_a_commit", "atom_a_finish", "atom_b_prepare", "atom_b_dependency", "atom_b_commit", "atom_b_finish")
PROFILE_HOOKS = ("atom_a_prepare", "atom_b_prepare", "atom_a_dependency", "atom_b_dependency", "atom_b_commit", "atom_a_finish")


def read(name: str) -> object:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def write_json(path: Path, value: object) -> None:
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def event_rules(names: list[str]) -> dict:
    return {name: {"initial_version": 0, "system": False, "program_signalable": True, "program_clearable": True} for name in names}


def source_from(lines: dict[str, list[str]]) -> str:
    output = []
    for hook in HOOKS:
        output.append(f"async def {hook}(robot):")
        output.extend(lines[hook] or ["    pass"])
    return "\n".join(output) + "\n"


def _literal_or_marker(node: ast.AST) -> object:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        return "<dynamic_receipt>"
    return "<number_within_public_range>" if isinstance(value, (int, float)) else value


def required_hook_calls(source: str) -> dict[str, list[dict]]:
    """Expose the treatment-critical hook placement used by qualification."""
    tree = ast.parse(source)
    output = {}
    for function in (node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)):
        rows = []
        for statement in function.body:
            value = statement.value if isinstance(statement, (ast.Expr, ast.Assign)) else None
            awaited = isinstance(value, ast.Await)
            call = value.value if awaited else value
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "robot"):
                continue
            rows.append({
                "method": call.func.attr,
                "args": [_literal_or_marker(argument) for argument in call.args],
                "awaited": awaited,
                "required_keywords": sorted(keyword.arg for keyword in call.keywords if keyword.arg),
            })
        output[function.name] = rows
    return output


def finalize_assets(spec: dict, lines: dict[str, list[str]]) -> str:
    source = source_from(lines)
    spec["public_task"]["required_hook_calls"] = required_hook_calls(source)
    return source


def add_context(lines: dict[str, list[str]], profile: int) -> None:
    hook = PROFILE_HOOKS[profile]
    arm = "LEFT" if hook.startswith("atom_a") else "RIGHT"
    lines[hook].insert(0, f'    await robot.inspect("{arm}", "context_fact_{profile}")')


def signal(lines: list[str], event: str) -> None:
    lines.append(f'    robot.signal("{event}")')


def wait(lines: list[str], event: str, variable: str) -> None:
    lines.append(f'    {variable} = await robot.wait_event("{event}", 20)')


def clear(lines: list[str], event: str, variable: str) -> None:
    lines.append(f'    robot.clear_event("{event}", expected_version={variable}.version)')


def public_protocol(row: dict, topology: dict) -> list[str]:
    family_id, kind, resource = row["id"], topology["oracle_kind"], row["shared_resource"]
    if kind == "OCCUPANCY_OVERLAP":
        prereq = [event for event in topology["events"] if event != "tool_taken"]
        return [
            f'LEFT acquires "{resource}", approaches, occupies a_zone, exits to left_exit, and establishes these prerequisites in the required hooks: {prereq or ["no prerequisite event"]}.',
            f'RIGHT waits for every listed prerequisite event, acquires "{resource}", enters b_zone, exits to right_exit, releases it, and clears all events.',
            "Neither gripper may occupy the shared critical volume at the same time.",
        ]
    if kind in {"POSE_SUPPORT_DURING_ACTION", "CLEARANCE_BEFORE_ACTION"}:
        ready, b_pre, commit, a_pose, protected = SUPPORT_MAP[family_id]
        return [
            f'LEFT acquires "{resource}", moves to {a_pose}, and signals {ready}; it stays there and retains the resource until completion.',
            f'RIGHT waits for {ready}, signals any required intermediate milestones {b_pre}, performs the protected move to {protected}, then signals {commit}.',
            f'LEFT clears the milestones and releases "{resource}" only after {commit}; both arms return home.',
        ]
    if kind == "RELEASE_BEFORE_COMMIT":
        ready, stages, commit = COMMIT_MAP[family_id]
        stage_hook = COMMIT_STAGE_HOOK[family_id]
        return [
            f'LEFT acquires and physically establishes "{resource}", then signals {ready}.',
            f'RIGHT waits for {ready}; its required intermediate milestones {stages} are emitted in {stage_hook}; it performs the dependent action and signals {commit}.',
            f'LEFT must keep "{resource}" until every intermediate milestone and {commit}, then clears events, releases, and returns home.',
        ]
    if kind == "RECOVERY_OCCUPANCY":
        release = "zone_released" if family_id == "R2V4-F13" else "corridor_released"
        return [f'LEFT owns "{resource}" while occupying a_zone, exits and releases it, then signals {release}.', f'RIGHT waits for {release} before entering b_zone, exits, clears the event, and returns home.', "The two critical occupancy intervals must not overlap."]
    if kind == "QUARANTINE_OBJECT":
        return [f'LEFT acquires "{resource}", establishes quarantine, signals quarantine_ready and then quarantine_commit.', "RIGHT waits for quarantine_commit, moves replacement_part from replacement_source to recovered_bin, never grasps or moves dropped_part, and signals recovery_done.", "RIGHT clears all events; dropped_part remains at drop_zone and both arms return home."]
    if kind == "HOLD_ACK_BEFORE_RELEASE":
        return [f'LEFT acquires "{resource}", signals stop_started and then hold_ack.', "RIGHT acquires payload_hold during preparation but must wait for hold_ack before releasing payload_hold; it then signals payload_released.", "RIGHT clears all events and both arms return home."]
    if kind == "REROUTE_OBJECT_BEFORE_CLEANUP":
        return [f'LEFT acquires "{resource}", grasps rejected_part at reject_source, signals reject_declared, places it at reject_bin, then signals reroute_commit.', "RIGHT waits for reroute_commit before moving into original_route and then signals cleanup_done.", "RIGHT clears all events; rejected_part remains at reject_bin and both arms return home."]
    if kind == "CLAMP_COMMIT_BEFORE_JAM_CLEAR":
        return [f'LEFT acquires "{resource}", signals clamp_active and then safe_release_commit before releasing the resource.', "RIGHT waits for safe_release_commit before entering right_protected for jam clearance, then signals jam_cleared.", "RIGHT clears all events and both arms return home."]
    raise ValueError(kind)


def base_spec(row: dict, contract: dict, topology: dict, profile: int) -> dict:
    coordinates = {
        "left_home": [-2.0, 0.0, 1.0], "right_home": [2.0, 0.0, 1.0],
        "left_approach": [-1.0, -0.3 + 0.04 * profile, 1.0], "right_approach": [1.0, 0.3 - 0.04 * profile, 1.0],
        "a_zone": [0.0, -0.01 * profile, 1.0], "b_zone": [0.0, -0.01 * profile, 1.0],
        "left_exit": [-1.0, 1.0, 1.0], "right_exit": [1.0, 1.0, 1.0],
        "right_protected": [0.0, 0.0, 1.0], "support_pose": [-0.15, 0.0, 1.0], "barrier_pose": [-0.2, 0.0, 1.0],
        "drop_zone": [-0.8, 0.5, 0.8], "replacement_source": [0.8, -0.5, 0.8], "recovered_bin": [0.8, 0.6, 0.8],
        "reject_source": [-0.8, -0.5, 0.8], "reject_bin": [-0.8, 0.6, 0.8], "original_route": [0.2, 0.6, 1.0],
    }
    initial = {"LEFT": "left_home", "RIGHT": "right_home"}
    goals = {"LEFT": "left_home", "RIGHT": "right_home"}
    object_sizes, supports = {}, []
    if topology["oracle_kind"] == "QUARANTINE_OBJECT":
        initial.update(dropped_part="drop_zone", replacement_part="replacement_source")
        goals.update(dropped_part="drop_zone", replacement_part="recovered_bin")
        object_sizes = {"dropped_part": [0.03, 0.03, 0.03], "replacement_part": [0.03, 0.03, 0.03]}
        supports = ["drop_zone", "replacement_source", "recovered_bin"]
    elif topology["oracle_kind"] == "REROUTE_OBJECT_BEFORE_CLEANUP":
        initial["rejected_part"] = "reject_source"; goals["rejected_part"] = "reject_bin"
        object_sizes = {"rejected_part": [0.03, 0.03, 0.03]}; supports = ["reject_source", "reject_bin"]
    facts = {f"neutral_fact_{index}": {"initial_version": 1, "value_schema": {"const": True}} for index in range(3)}
    facts[f"context_fact_{profile}"] = {"initial_version": 1, "value_schema": {"const": {"family_id": row["id"], "contract_ready": True}}}
    return {
        "task_id": row["id"], "family_id": row["id"], "axis_id": "RQ2_RECOMPOSITION_V4", "variant": "A",
        "world": {"geometry_model": "TRANSLATION_AABB_FIXED_ORIENTATION", "pose_coordinates_m": coordinates, "modeled_solids": ["LEFT_gripper", "RIGHT_gripper", *object_sizes], "gripper_half_size_m": [0.03, 0.03, 0.03], "object_half_size_m": object_sizes, "logical_supports": supports, "collision_pairs": [["LEFT_gripper", "RIGHT_gripper"]], "excluded_pairs": [], "grasp_offsets_m": {}, "invalidation_on_release": {}, "contact_allowances": [], "approach_sequences": []},
        "pair_constants": {"initial": initial, "goals": goals, "deadline_s": 60, "default_move_timeout_s": 4, "explicit_move_timeout_range_s": [0.05, 30], "durations_s": {"grasp": 0.1, "release": 0.1, "inspect": 0.1, "refresh": 0.1, "hold": 0.1, "safe_stop": 0.1, "reset_failure": 0.1, "acquire": 0.1, "release_resource": 0.1, "set_mode": 0.1, "wait_event": 0.1, "move": 1.0}},
        "public_task": {"scene": row["task_goal"], "deadline_s": 60, "atom_a_role": contract["a_role"], "atom_b_role": contract["b_role"], "safety_requirement": contract["safe_predicate"], "goal": ["complete both local roles", "satisfy all declared object goals", "return both arms home", "leave all resources free and events inactive"], "required_context_check": {"hook": PROFILE_HOOKS[profile], "call": f'await robot.inspect("{("LEFT" if PROFILE_HOOKS[profile].startswith("atom_a") else "RIGHT")}", "context_fact_{profile}")'}, "atomic_hook_contract": {"prepare": "approach and establish prerequisites", "dependency": "produce or consume the critical relation", "commit": "complete or acknowledge the critical relation", "finish": "clean up and return the assigned arm home"}, "local_coordination_protocol": public_protocol(row, topology), "direct_P_trigger": topology["p_trigger"]},
        "observation_facts": facts, "state_facts": {}, "events": event_rules(topology["events"]), "resources": {row["shared_resource"]: {"initial_mode": "OFF"}},
        "h_variant": {"invalidates": True}, "failure": {"injected": False}, "development_contract": {},
        "experimental_assignment": {"study": "RQ2_STRUCTURE_PRESERVING_RECOMPOSITION_V4", "mechanism": row["mechanism"], "oracle_kind": topology["oracle_kind"], "topology_id": topology["topology_id"], "semantic_profile": profile, "future_factor_labels_visible_to_generator": False},
    }


def exclusive_assets(spec: dict, row: dict, topology: dict, profile: int) -> str:
    resource, events = row["shared_resource"], topology["events"]
    b_ack = [event for event in events if event == "tool_taken"]
    prereq = [event for event in events if event not in b_ack]
    lines = {
        "atom_a_prepare": [f'    await robot.acquire("LEFT", "{resource}", 20)', '    await robot.move("LEFT", "left_approach", 4)'],
        "atom_a_dependency": ['    await robot.move("LEFT", "a_zone", 4)'], "atom_a_commit": ['    await robot.move("LEFT", "left_exit", 4)'],
        "atom_a_finish": [f'    await robot.release_resource("LEFT", "{resource}")', '    await robot.move("LEFT", "left_home", 4)'],
        "atom_b_prepare": ['    await robot.move("RIGHT", "right_approach", 4)'], "atom_b_dependency": [],
        "atom_b_commit": ['    await robot.move("RIGHT", "right_exit", 4)'], "atom_b_finish": [f'    await robot.release_resource("RIGHT", "{resource}")'],
    }
    producer_hooks = {
        "R2V4-F02": {"drawer_stable": "atom_a_dependency"},
        "R2V4-F03": {"dispense_complete": "atom_a_dependency", "station_purged": "atom_a_commit"},
        "R2V4-F17": {"laser_off": "atom_a_commit", "guard_clear": "atom_a_finish"},
    }.get(row["id"], {})
    for event in prereq:
        hook = producer_hooks.get(event, "atom_a_commit")
        if hook == "atom_a_finish":
            lines[hook].insert(-1, f'    robot.signal("{event}")')
        else:
            signal(lines[hook], event)
        wait(lines["atom_b_dependency"], event, "receipt_" + event)
    lines["atom_b_dependency"].extend([f'    await robot.acquire("RIGHT", "{resource}", 20)', '    await robot.move("RIGHT", "b_zone", 4)'])
    for event in b_ack: signal(lines["atom_b_commit"], event)
    for event in events:
        wait(lines["atom_b_finish"], event, "final_" + event); clear(lines["atom_b_finish"], event, "final_" + event)
    lines["atom_b_finish"].append('    await robot.move("RIGHT", "right_home", 4)')
    add_context(lines, profile)
    spec["rq2_direct_p_contract"] = {"oracle_kind": topology["oracle_kind"], "mechanism": row["mechanism"], "a_zone_pose": "a_zone", "b_zone_pose": "b_zone", "a_exit_poses": ["left_exit", "left_home"], "b_exit_poses": ["right_exit", "right_home"], "required_events_before_b": prereq, "event_producer_hooks": {event: producer_hooks.get(event, "atom_a_commit") for event in prereq}}
    return finalize_assets(spec, lines)


SUPPORT_MAP = {
    "R2V4-F05": (["support_ready"], [], "b_committed", "support_pose", "right_protected"),
    "R2V4-F06": (["aperture_clear"], [], "lid_closed", "left_exit", "right_protected"),
    "R2V4-F07": (["support_ready"], ["transfer_started"], "stable_commit", "support_pose", "right_protected"),
    "R2V4-F08": (["fixture_stable", "force_ready"], [], "peg_seated", "support_pose", "right_protected"),
    "R2V4-F19": (["barrier_deployed"], [], "lower_zone_clear", "barrier_pose", "b_zone"),
    "R2V4-F20": (["counterforce_ready", "torque_ready"], [], "axle_seated", "support_pose", "right_protected"),
}


def support_assets(spec: dict, row: dict, topology: dict, profile: int) -> str:
    resource = row["shared_resource"]
    ready_events, b_pre_events, commit_event, a_pose, protected_pose = SUPPORT_MAP[row["id"]]
    lines = {
        "atom_a_prepare": [f'    await robot.acquire("LEFT", "{resource}", 20)', '    await robot.move("LEFT", "left_approach", 4)'],
        "atom_a_dependency": [f'    await robot.move("LEFT", "{a_pose}", 4)'], "atom_a_commit": [],
        "atom_a_finish": [f'    await robot.release_resource("LEFT", "{resource}")', '    await robot.move("LEFT", "left_home", 4)'],
        "atom_b_prepare": ['    await robot.move("RIGHT", "right_approach", 4)'], "atom_b_dependency": [], "atom_b_commit": [],
        "atom_b_finish": ['    await robot.move("RIGHT", "right_home", 4)'],
    }
    for event in ready_events:
        signal(lines["atom_a_dependency"], event); wait(lines["atom_b_dependency"], event, "ready_" + event)
    for event in b_pre_events: signal(lines["atom_b_dependency"], event)
    lines["atom_b_dependency"].append(f'    await robot.move("RIGHT", "{protected_pose}", 4)')
    signal(lines["atom_b_commit"], commit_event)
    cleanup_events = [*b_pre_events, commit_event, *ready_events]
    # Observe the whole completion chain before clearing any milestone.  Some
    # milestones (for example transfer_started) are part of the protected
    # interval and must remain active through the protected action's complete
    # event, not merely through its start event.
    for event in cleanup_events:
        wait(lines["atom_a_commit"], event, "cleanup_" + event)
    for event in cleanup_events:
        clear(lines["atom_a_commit"], event, "cleanup_" + event)
    add_context(lines, profile)
    spec["rq2_direct_p_contract"] = {"oracle_kind": topology["oracle_kind"], "mechanism": row["mechanism"], "protected_action": "move", "protected_args": {"arm": "RIGHT", "pose": protected_pose}, "required_a_pose": a_pose, "required_resource": resource, "required_owner": "LEFT", "required_events": [*ready_events, *b_pre_events], "a_ready_events": ready_events, "b_pre_events": b_pre_events, "commit_event": commit_event}
    return finalize_assets(spec, lines)


COMMIT_MAP = {
    "R2V4-F09": ("hold_ready", [], "consumer_commit"), "R2V4-F10": ("tension_ready", ["threaded"], "consumer_commit"),
    "R2V4-F11": ("compression_ready", ["latch_checked"], "consumer_commit"), "R2V4-F12": ("left_press_ready", ["right_press_ready"], "consumer_commit"),
    "R2V4-F21": ("alignment_ready", ["lock_started", "engagement_checked"], "consumer_commit"), "R2V4-F22": ("clamp_ready", ["cure_checked"], "consumer_commit"),
}

COMMIT_STAGE_HOOK = {
    "R2V4-F09": "atom_b_dependency",
    "R2V4-F10": "atom_b_dependency",
    "R2V4-F11": "atom_b_commit",
    "R2V4-F12": "atom_b_prepare",
    "R2V4-F21": "atom_b_dependency",
    "R2V4-F22": "atom_b_finish",
}


def commit_assets(spec: dict, row: dict, topology: dict, profile: int) -> str:
    resource = row["shared_resource"]
    ready_event, stage_events, commit_event = COMMIT_MAP[row["id"]]
    lines = {
        "atom_a_prepare": [f'    await robot.acquire("LEFT", "{resource}", 20)', '    await robot.move("LEFT", "a_zone", 4)'], "atom_a_dependency": [], "atom_a_commit": [],
        "atom_a_finish": [f'    await robot.release_resource("LEFT", "{resource}")', '    await robot.move("LEFT", "left_home", 4)'],
        "atom_b_prepare": ['    await robot.move("RIGHT", "right_approach", 4)'], "atom_b_dependency": [], "atom_b_commit": [], "atom_b_finish": ['    await robot.move("RIGHT", "right_home", 4)'],
    }
    signal(lines["atom_a_dependency"], ready_event); wait(lines["atom_b_dependency"], ready_event, "ready")
    stage_hook = COMMIT_STAGE_HOOK[row["id"]]
    for event in stage_events:
        if stage_hook == "atom_b_finish":
            lines[stage_hook].insert(0, f'    robot.signal("{event}")')
        else:
            signal(lines[stage_hook], event)
    lines["atom_b_dependency"].append('    await robot.move("RIGHT", "right_protected", 4)'); signal(lines["atom_b_commit"], commit_event)
    for event in [*stage_events, commit_event, ready_event]:
        wait(lines["atom_a_commit"], event, "done_" + event); clear(lines["atom_a_commit"], event, "done_" + event)
    add_context(lines, profile)
    spec["rq2_direct_p_contract"] = {"oracle_kind": topology["oracle_kind"], "mechanism": row["mechanism"], "release_action": "release_resource", "release_args": {"arm": "LEFT", "resource_id": resource}, "ready_event": ready_event, "commit_event": commit_event, "required_prior_events": stage_events, "stage_hook": stage_hook}
    return finalize_assets(spec, lines)


def recovery_assets(spec: dict, row: dict, topology: dict, profile: int) -> str:
    kind, resource = topology["oracle_kind"], row["shared_resource"]
    if kind == "RECOVERY_OCCUPANCY":
        active_event = "dependency_active" if row["id"] == "R2V4-F13" else "obstruction_seen"
        release_event = "zone_released" if row["id"] == "R2V4-F13" else "corridor_released"
        lines = {"atom_a_prepare": [f'    await robot.acquire("LEFT", "{resource}", 20)', '    await robot.move("LEFT", "left_approach", 4)'], "atom_a_dependency": ['    await robot.move("LEFT", "a_zone", 4)'], "atom_a_commit": ['    await robot.move("LEFT", "left_exit", 4)'], "atom_a_finish": [f'    await robot.release_resource("LEFT", "{resource}")'], "atom_b_prepare": ['    await robot.move("RIGHT", "right_approach", 4)'], "atom_b_dependency": [], "atom_b_commit": ['    await robot.move("RIGHT", "right_exit", 4)'], "atom_b_finish": []}
        signal(lines["atom_a_dependency"], active_event); wait(lines["atom_a_finish"], active_event, "active"); clear(lines["atom_a_finish"], active_event, "active"); signal(lines["atom_a_finish"], release_event); lines["atom_a_finish"].append('    await robot.move("LEFT", "left_home", 4)')
        wait(lines["atom_b_dependency"], release_event, "released")
        if row["id"] == "R2V4-F23": signal(lines["atom_b_dependency"], "detour_ready")
        lines["atom_b_dependency"].append('    await robot.move("RIGHT", "b_zone", 4)')
        for event in ([release_event, "detour_ready"] if row["id"] == "R2V4-F23" else [release_event]):
            wait(lines["atom_b_finish"], event, "released_final_" + event); clear(lines["atom_b_finish"], event, "released_final_" + event)
        lines["atom_b_finish"].append('    await robot.move("RIGHT", "right_home", 4)')
        spec["rq2_direct_p_contract"] = {"oracle_kind": kind, "mechanism": row["mechanism"], "a_zone_pose": "a_zone", "b_zone_pose": "b_zone", "a_exit_poses": ["left_exit", "left_home"], "b_exit_poses": ["right_exit", "right_home"], "required_release_event": release_event}
    elif kind == "QUARANTINE_OBJECT":
        lines = {"atom_a_prepare": [f'    await robot.acquire("LEFT", "{resource}", 20)', '    await robot.move("LEFT", "a_zone", 4)'], "atom_a_dependency": [], "atom_a_commit": [], "atom_a_finish": [f'    await robot.release_resource("LEFT", "{resource}")', '    await robot.move("LEFT", "left_home", 4)'], "atom_b_prepare": ['    await robot.move("RIGHT", "replacement_source", 4)'], "atom_b_dependency": [], "atom_b_commit": [], "atom_b_finish": []}
        signal(lines["atom_a_dependency"], "quarantine_ready"); signal(lines["atom_a_commit"], "quarantine_commit"); wait(lines["atom_b_dependency"], "quarantine_commit", "quarantine")
        lines["atom_b_dependency"].extend(['    await robot.grasp("RIGHT", "replacement_part")', '    await robot.move("RIGHT", "recovered_bin", 4)', '    await robot.release("RIGHT", "replacement_part", "recovered_bin")']); signal(lines["atom_b_commit"], "recovery_done")
        for event in topology["events"]:
            wait(lines["atom_b_finish"], event, "cleanup_" + event); clear(lines["atom_b_finish"], event, "cleanup_" + event)
        lines["atom_b_finish"].append('    await robot.move("RIGHT", "right_home", 4)')
        spec["rq2_direct_p_contract"] = {"oracle_kind": kind, "mechanism": row["mechanism"], "quarantined_object": "dropped_part", "replacement_object": "replacement_part", "quarantine_commit_event": "quarantine_commit", "recovery_action": "grasp", "recovery_args": {"arm": "RIGHT", "object_id": "replacement_part"}}
    elif kind == "HOLD_ACK_BEFORE_RELEASE":
        payload_resource = "payload_hold"; spec["resources"][payload_resource] = {"initial_mode": "OFF"}
        lines = {"atom_a_prepare": [f'    await robot.acquire("LEFT", "{resource}", 20)', '    await robot.move("LEFT", "a_zone", 4)'], "atom_a_dependency": [], "atom_a_commit": [], "atom_a_finish": [f'    await robot.release_resource("LEFT", "{resource}")', '    await robot.move("LEFT", "left_home", 4)'], "atom_b_prepare": [f'    await robot.acquire("RIGHT", "{payload_resource}", 20)', '    await robot.move("RIGHT", "right_approach", 4)'], "atom_b_dependency": [], "atom_b_commit": ['    await robot.move("RIGHT", "right_exit", 4)'], "atom_b_finish": []}
        signal(lines["atom_a_dependency"], "stop_started"); signal(lines["atom_a_commit"], "hold_ack"); wait(lines["atom_b_dependency"], "hold_ack", "ack"); lines["atom_b_dependency"].append(f'    await robot.release_resource("RIGHT", "{payload_resource}")'); signal(lines["atom_b_dependency"], "payload_released")
        for event in topology["events"]:
            wait(lines["atom_b_finish"], event, "cleanup_" + event); clear(lines["atom_b_finish"], event, "cleanup_" + event)
        lines["atom_b_finish"].append('    await robot.move("RIGHT", "right_home", 4)')
        spec["rq2_direct_p_contract"] = {"oracle_kind": kind, "mechanism": row["mechanism"], "release_action": "release_resource", "release_args": {"arm": "RIGHT", "resource_id": payload_resource}, "hold_ack_event": "hold_ack"}
    elif kind == "REROUTE_OBJECT_BEFORE_CLEANUP":
        lines = {"atom_a_prepare": [f'    await robot.acquire("LEFT", "{resource}", 20)', '    await robot.move("LEFT", "reject_source", 4)', '    await robot.grasp("LEFT", "rejected_part")'], "atom_a_dependency": [], "atom_a_commit": ['    await robot.move("LEFT", "reject_bin", 4)', '    await robot.release("LEFT", "rejected_part", "reject_bin")'], "atom_a_finish": [f'    await robot.release_resource("LEFT", "{resource}")', '    await robot.move("LEFT", "left_home", 4)'], "atom_b_prepare": ['    await robot.move("RIGHT", "right_approach", 4)'], "atom_b_dependency": [], "atom_b_commit": [], "atom_b_finish": []}
        signal(lines["atom_a_dependency"], "reject_declared"); signal(lines["atom_a_commit"], "reroute_commit"); wait(lines["atom_b_dependency"], "reroute_commit", "reroute"); lines["atom_b_dependency"].append('    await robot.move("RIGHT", "original_route", 4)'); signal(lines["atom_b_commit"], "cleanup_done")
        for event in topology["events"]:
            wait(lines["atom_b_finish"], event, "cleanup_" + event); clear(lines["atom_b_finish"], event, "cleanup_" + event)
        lines["atom_b_finish"].append('    await robot.move("RIGHT", "right_home", 4)')
        spec["rq2_direct_p_contract"] = {"oracle_kind": kind, "mechanism": row["mechanism"], "object_id": "rejected_part", "safe_destination": "reject_bin", "reroute_commit_event": "reroute_commit", "cleanup_action": "move", "cleanup_args": {"arm": "RIGHT", "pose": "original_route"}}
    elif kind == "CLAMP_COMMIT_BEFORE_JAM_CLEAR":
        lines = {"atom_a_prepare": [f'    await robot.acquire("LEFT", "{resource}", 20)', '    await robot.move("LEFT", "a_zone", 4)'], "atom_a_dependency": [], "atom_a_commit": [], "atom_a_finish": [f'    await robot.release_resource("LEFT", "{resource}")', '    await robot.move("LEFT", "left_home", 4)'], "atom_b_prepare": ['    await robot.move("RIGHT", "right_approach", 4)'], "atom_b_dependency": [], "atom_b_commit": [], "atom_b_finish": []}
        signal(lines["atom_a_dependency"], "clamp_active"); signal(lines["atom_a_commit"], "safe_release_commit"); wait(lines["atom_b_dependency"], "safe_release_commit", "safe_release"); lines["atom_b_dependency"].append('    await robot.move("RIGHT", "right_protected", 4)'); signal(lines["atom_b_commit"], "jam_cleared")
        for event in topology["events"]:
            wait(lines["atom_b_finish"], event, "cleanup_" + event); clear(lines["atom_b_finish"], event, "cleanup_" + event)
        lines["atom_b_finish"].append('    await robot.move("RIGHT", "right_home", 4)')
        spec["rq2_direct_p_contract"] = {"oracle_kind": kind, "mechanism": row["mechanism"], "protected_action": "move", "protected_args": {"arm": "RIGHT", "pose": "right_protected"}, "safe_release_event": "safe_release_commit", "clamp_release_action": "release_resource", "clamp_release_args": {"arm": "LEFT", "resource_id": resource}}
    else:
        raise ValueError(kind)
    add_context(lines, profile)
    return finalize_assets(spec, lines)


def public_prompt(spec: dict) -> str:
    public = json.dumps(spec["public_task"], ensure_ascii=False, indent=2)
    resources, events = json.dumps(sorted(spec["resources"]), ensure_ascii=False), json.dumps(sorted(spec["events"]), ensure_ascii=False)
    facts, poses = json.dumps(sorted(spec["observation_facts"]), ensure_ascii=False), json.dumps(sorted(spec["world"]["pose_coordinates_m"]), ensure_ascii=False)
    objects = json.dumps(sorted(set(spec["pair_constants"]["initial"]) - {"LEFT", "RIGHT"}), ensure_ascii=False)
    supports = json.dumps(sorted(spec["world"]["logical_supports"]), ensure_ascii=False)
    return f'''Implement the two atomic robot-task modules below.

Return exactly one Python code block containing exactly these eight top-level async functions, in this order:
{', '.join(HOOKS)}. Each accepts only robot. Do not define run_task, import modules, or create tasks/threads. Orchestration is supplied mechanically after generation and is not part of your output.

Relevant API forms:
- await robot.move(arm, pose, timeout_s)
- await robot.inspect(arm, fact_id)
- await robot.acquire(arm, resource_id, timeout_s)
- await robot.release_resource(arm, resource_id)
- await robot.grasp(arm, object_id)
- await robot.release(arm, object_id, support_zone)
- receipt = await robot.wait_event(event_id, timeout_s)
- receipt = robot.signal(event_id)
- robot.clear_event(event_id, expected_version=receipt.version)
Use only declared identifiers. signal and clear_event are synchronous; other listed calls are awaited.
The overall task deadline is 60 s, but it is NOT a legal per-call timeout. Every
timeout_s argument must be in the public range [0.05, 30]. Use 4 for move and
20 for acquire/wait_event unless the hook contract requires no timeout.
For each function, include every entry in public_task.required_hook_calls in
the listed order and in that exact hook. The numeric marker means any timeout
inside the public range. Additional calls are allowed only when they use the
declared API/identifiers and do not remove or relocate the required calls.
Declared resources: {resources}
Declared events: {events}
Declared observation facts: {facts}
Declared poses: {poses}
Declared objects: {objects}
Declared object supports: {supports}

PUBLIC TASK
{public}
'''


def main() -> None:
    if (HERE / "SCIENTIFIC_FREEZE.json").exists(): raise RuntimeError("scientific freeze exists")
    blueprint = read("FAMILY_BLUEPRINT.json"); contracts = {row["id"]: row for row in read("FAMILY_CONTRACTS.json")["families"]}; topologies = {row["id"]: row for row in read("FAMILY_TOPOLOGIES.json")["families"]}
    counters, catalog = defaultdict(int), []
    for row in blueprint["families"]:
        mechanism = row["mechanism"]; profile = counters[mechanism]; counters[mechanism] += 1; contract, topology = contracts[row["id"]], topologies[row["id"]]
        spec = base_spec(row, contract, topology, profile)
        if mechanism == "EXCLUSIVE_MOTION_VOLUME_OVERLAP": source = exclusive_assets(spec, row, topology, profile)
        elif mechanism == "SUPPORT_OR_BARRIER_VIOLATION": source = support_assets(spec, row, topology, profile)
        elif mechanism == "CLEAR_OR_RELEASE_BEFORE_COMMIT": source = commit_assets(spec, row, topology, profile)
        else: source = recovery_assets(spec, row, topology, profile)
        directory = OUT / row["id"]; write_json(directory / "SPEC.json", spec); write(directory / "reference_atoms.py", source); write(directory / "PROMPT.txt", public_prompt(spec))
        catalog.append({"family_id": row["id"], "mechanism": mechanism, "oracle_kind": topology["oracle_kind"], "topology_id": topology["topology_id"], "semantic_profile": profile, "serial_policy": topology["serial_policy"], "spec_path": str((directory / "SPEC.json").relative_to(HERE)), "reference_source_path": str((directory / "reference_atoms.py").relative_to(HERE)), "prompt_path": str((directory / "PROMPT.txt").relative_to(HERE))})
    write_json(HERE / "REFERENCE_TASK_CATALOG.json", catalog)
    print(json.dumps({"status": "BUILT_V4", "families": len(catalog), "mechanisms": dict(counters)}, ensure_ascii=False))


if __name__ == "__main__": main()
