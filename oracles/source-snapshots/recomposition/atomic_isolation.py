"""Condition-blind, family-specific counterpart fixtures for atomic qualification."""
from __future__ import annotations

from frozen_composer import validate_atomic_source


def _signal(lines: list[str], event: str) -> None:
    lines.append(f'    robot.signal("{event}")')


def _clear(lines: list[str], event: str, prefix: str = "fixture") -> None:
    variable = f"{prefix}_{event}"
    lines.extend([f'    {variable} = await robot.wait_event("{event}", 20)', f'    robot.clear_event("{event}", expected_version={variable}.version)'])


def compose_atomic_isolation(source: str, spec: dict, atom: str) -> str:
    validate_atomic_source(source)
    if atom not in {"A", "B"}: raise ValueError("atom must be A or B")
    contract = spec["rq2_direct_p_contract"]
    kind = contract["oracle_kind"]
    resource = next(iter(spec.get("resources", {})), None)
    events = list(spec.get("events", {}))
    lines = [source.rstrip(), "async def run_task(robot):"]
    if atom == "A":
        lines.extend(["    await atom_a_prepare(robot)", "    await atom_a_dependency(robot)"])
        if kind in {"POSE_SUPPORT_DURING_ACTION", "CLEARANCE_BEFORE_ACTION"}:
            for event in contract["b_pre_events"]:
                _signal(lines, event)
            _signal(lines, contract["commit_event"])
        elif kind == "RELEASE_BEFORE_COMMIT":
            for event in contract.get("required_prior_events", []): _signal(lines, event)
            _signal(lines, contract["commit_event"])
        lines.extend(["    await atom_a_commit(robot)", "    await atom_a_finish(robot)"])
        # A-only qualification must clean only events produced by A.  Waiting
        # for B-produced completion events would turn a correct isolated atom
        # into a fixture deadlock and would not test A's local contract.
        if kind == "OCCUPANCY_OVERLAP":
            for event in contract.get("required_events_before_b", []): _clear(lines, event)
        elif kind == "RECOVERY_OCCUPANCY":
            _clear(lines, contract["required_release_event"])
        elif kind == "QUARANTINE_OBJECT":
            for event in ("quarantine_ready", contract["quarantine_commit_event"]): _clear(lines, event)
        elif kind == "HOLD_ACK_BEFORE_RELEASE":
            for event in ("stop_started", contract["hold_ack_event"]): _clear(lines, event)
        elif kind == "REROUTE_OBJECT_BEFORE_CLEANUP":
            for event in ("reject_declared", contract["reroute_commit_event"]): _clear(lines, event)
        elif kind == "CLAMP_COMMIT_BEFORE_JAM_CLEAR":
            for event in ("clamp_active", contract["safe_release_event"]): _clear(lines, event)
    elif kind == "OCCUPANCY_OVERLAP":
        for event in contract.get("required_events_before_b", []): _signal(lines, event)
        lines.extend(["    await atom_b_prepare(robot)", "    await atom_b_dependency(robot)", "    await atom_b_commit(robot)", "    await atom_b_finish(robot)"])
    elif kind in {"POSE_SUPPORT_DURING_ACTION", "CLEARANCE_BEFORE_ACTION"}:
        lines.extend([f'    await robot.acquire("LEFT", "{resource}", 20)', f'    await robot.move("LEFT", "{contract["required_a_pose"]}", 4)'])
        for event in contract["a_ready_events"]: _signal(lines, event)
        lines.extend(["    await atom_b_prepare(robot)", "    await atom_b_dependency(robot)", "    await atom_b_commit(robot)", "    await atom_b_finish(robot)"])
        for event in events: _clear(lines, event)
        lines.extend([f'    await robot.release_resource("LEFT", "{resource}")', '    await robot.move("LEFT", "left_home", 4)'])
    elif kind == "RELEASE_BEFORE_COMMIT":
        lines.append(f'    await robot.acquire("LEFT", "{resource}", 20)'); _signal(lines, contract["ready_event"])
        lines.extend(["    await atom_b_prepare(robot)", "    await atom_b_dependency(robot)", "    await atom_b_commit(robot)", "    await atom_b_finish(robot)"])
        for event in events: _clear(lines, event)
        lines.extend([f'    await robot.release_resource("LEFT", "{resource}")', '    await robot.move("LEFT", "left_home", 4)'])
    elif kind == "RECOVERY_OCCUPANCY":
        _signal(lines, contract["required_release_event"])
        lines.extend(["    await atom_b_prepare(robot)", "    await atom_b_dependency(robot)", "    await atom_b_commit(robot)", "    await atom_b_finish(robot)"])
    elif kind == "QUARANTINE_OBJECT":
        _signal(lines, "quarantine_ready"); _signal(lines, contract["quarantine_commit_event"])
        lines.extend(["    await atom_b_prepare(robot)", "    await atom_b_dependency(robot)", "    await atom_b_commit(robot)", "    await atom_b_finish(robot)"])
    elif kind == "HOLD_ACK_BEFORE_RELEASE":
        _signal(lines, "stop_started"); _signal(lines, contract["hold_ack_event"])
        lines.extend(["    await atom_b_prepare(robot)", "    await atom_b_dependency(robot)", "    await atom_b_commit(robot)", "    await atom_b_finish(robot)"])
    elif kind == "REROUTE_OBJECT_BEFORE_CLEANUP":
        lines.extend(['    await robot.move("LEFT", "reject_source", 4)', '    await robot.grasp("LEFT", "rejected_part")', '    await robot.move("LEFT", "reject_bin", 4)', '    await robot.release("LEFT", "rejected_part", "reject_bin")'])
        _signal(lines, "reject_declared"); _signal(lines, contract["reroute_commit_event"])
        lines.extend(["    await atom_b_prepare(robot)", "    await atom_b_dependency(robot)", "    await atom_b_commit(robot)", "    await atom_b_finish(robot)", '    await robot.move("LEFT", "left_home", 4)'])
    elif kind == "CLAMP_COMMIT_BEFORE_JAM_CLEAR":
        _signal(lines, "clamp_active"); _signal(lines, contract["safe_release_event"])
        lines.extend(["    await atom_b_prepare(robot)", "    await atom_b_dependency(robot)", "    await atom_b_commit(robot)", "    await atom_b_finish(robot)"])
    else:
        raise ValueError(kind)
    return "\n".join(lines) + "\n"
