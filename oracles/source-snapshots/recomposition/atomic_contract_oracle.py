"""Frozen local-contract checks for condition-blind atomic qualification."""
from __future__ import annotations

import ast

from frozen_composer import EXPECTED_FUNCTIONS, validate_atomic_source


ARM_METHODS = {
    "move", "grasp", "release", "hold", "inspect", "refresh", "acquire",
    "release_resource", "set_mode", "safe_stop", "reset_failure",
}


def _literal(node: ast.AST) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _normalized_call_signature(statement: ast.stmt) -> dict | None:
    value = statement.value if isinstance(statement, (ast.Expr, ast.Assign)) else None
    awaited = isinstance(value, ast.Await)
    call = value.value if awaited else value
    if not (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "robot"
    ):
        return None
    args = []
    for argument in call.args:
        value = _literal(argument)
        args.append("<number_within_public_range>" if isinstance(value, (int, float)) else value)
    return {
        "method": call.func.attr,
        "args": args,
        "awaited": awaited,
        "required_keywords": sorted(keyword.arg for keyword in call.keywords if keyword.arg),
    }


def _signature_subsequence(actual: list[dict], required: list[dict]) -> bool:
    cursor = 0
    for expected in required:
        while cursor < len(actual) and actual[cursor] != expected:
            cursor += 1
        if cursor == len(actual):
            return False
        cursor += 1
    return True


def static_local_contract(source: str, spec: dict) -> dict:
    tree = validate_atomic_source(source)
    resources = set(spec.get("resources", {}))
    events = set(spec.get("events", {}))
    facts = set(spec.get("observation_facts", {})) | set(spec.get("state_facts", {}))
    poses = set(spec["world"]["pose_coordinates_m"])
    objects = set(spec["pair_constants"]["initial"]) - {"LEFT", "RIGHT"}
    supports = set(spec["world"].get("logical_supports", []))
    errors = []
    functions = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}
    for function_name in EXPECTED_FUNCTIONS:
        expected_arm = "LEFT" if function_name.startswith("atom_a_") else "RIGHT"
        for call in (node for node in ast.walk(functions[function_name]) if isinstance(node, ast.Call)):
            if not (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "robot"
            ):
                continue
            method = call.func.attr
            args = [_literal(argument) for argument in call.args]
            if method in ARM_METHODS:
                if not args or args[0] != expected_arm:
                    errors.append(f"{function_name}:{method}:ARM_MUST_BE_{expected_arm}")
            if method == "move" and (len(args) < 2 or args[1] not in poses):
                errors.append(f"{function_name}:move:UNDECLARED_OR_DYNAMIC_POSE")
            elif method in {"acquire", "release_resource", "set_mode"} and (len(args) < 2 or args[1] not in resources):
                errors.append(f"{function_name}:{method}:UNDECLARED_OR_DYNAMIC_RESOURCE")
            elif method in {"wait_event", "signal", "clear_event"} and (not args or args[0] not in events):
                errors.append(f"{function_name}:{method}:UNDECLARED_OR_DYNAMIC_EVENT")
            elif method in {"inspect", "refresh"} and (len(args) < 2 or args[1] not in facts):
                errors.append(f"{function_name}:{method}:UNDECLARED_OR_DYNAMIC_FACT")
            elif method in {"grasp", "hold"} and (len(args) < 2 or args[1] not in objects):
                errors.append(f"{function_name}:{method}:UNDECLARED_OR_DYNAMIC_OBJECT")
            elif method == "release" and (len(args) < 3 or args[1] not in objects or args[2] not in supports):
                errors.append(f"{function_name}:release:UNDECLARED_OBJECT_OR_SUPPORT")
            timeout_index = {"move": 2, "acquire": 2, "wait_event": 1}.get(method)
            if timeout_index is not None:
                timeout = args[timeout_index] if len(args) > timeout_index else None
                lower, upper = spec["pair_constants"]["explicit_move_timeout_range_s"]
                if not isinstance(timeout, (int, float)) or not lower <= timeout <= upper:
                    errors.append(f"{function_name}:{method}:TIMEOUT_OUTSIDE_PUBLIC_RANGE")
            if method == "clear_event" and "expected_version" not in {keyword.arg for keyword in call.keywords}:
                errors.append(f"{function_name}:clear_event:EXPECTED_VERSION_REQUIRED")
    for hook, required_calls in spec["public_task"].get("required_hook_calls", {}).items():
        actual_calls = [signature for statement in functions[hook].body if (signature := _normalized_call_signature(statement)) is not None]
        if not _signature_subsequence(actual_calls, required_calls):
            errors.append(f"{hook}:REQUIRED_HOOK_CALLS_MISSING_OR_REORDERED")
    required = spec["public_task"]["required_context_check"]
    required_hook = required["hook"]
    expected_arm = "LEFT" if required_hook.startswith("atom_a_") else "RIGHT"
    expected_fact = required["call"].split('"')[3]
    found_required = any(
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "robot"
        and call.func.attr == "inspect"
        and len(call.args) >= 2
        and _literal(call.args[0]) == expected_arm
        and _literal(call.args[1]) == expected_fact
        for call in ast.walk(functions[required_hook])
        if isinstance(call, ast.Call)
    )
    if not found_required:
        errors.append("REQUIRED_CONTEXT_CHECK_MISSING_FROM_DECLARED_HOOK")
    return {"passed": not errors, "errors": sorted(set(errors))}


def _events(capture: dict) -> list[dict]:
    return [event for event in capture.get("trusted_events", []) if event.get("phase") == "complete"]


def _matches(event: dict, action: str, required_args: dict) -> bool:
    return event.get("action") == action and all(event.get("args", {}).get(key) == value for key, value in required_args.items())


def _subsequence(events: list[dict], steps: list[tuple[str, dict]]) -> bool:
    cursor = 0
    for action, required_args in steps:
        while cursor < len(events) and not _matches(events[cursor], action, required_args):
            cursor += 1
        if cursor == len(events):
            return False
        cursor += 1
    return True


def required_steps(spec: dict, atom: str) -> list[tuple[str, dict]]:
    contract = spec["rq2_direct_p_contract"]
    kind = contract["oracle_kind"]
    primary_resource = next(iter(spec.get("resources", {})))
    if kind == "HOLD_ACK_BEFORE_RELEASE" and atom == "A":
        resource = primary_resource
    else:
        resource = contract.get("release_args", {}).get("resource_id") or contract.get("clamp_release_args", {}).get("resource_id") or primary_resource
    if kind == "OCCUPANCY_OVERLAP":
        if atom == "A":
            steps = [
                ("acquire", {"arm": "LEFT", "resource_id": resource}),
                ("move", {"arm": "LEFT", "pose": "a_zone"}),
            ]
            by_hook = contract.get("event_producer_hooks", {})
            steps.extend(("signal", {"event_id": event}) for event in contract.get("required_events_before_b", []) if by_hook.get(event) == "atom_a_dependency")
            steps.append(("move", {"arm": "LEFT", "pose": "left_exit"}))
            steps.extend(("signal", {"event_id": event}) for event in contract.get("required_events_before_b", []) if by_hook.get(event, "atom_a_commit") == "atom_a_commit")
            steps.extend([
                ("release_resource", {"arm": "LEFT", "resource_id": resource}),
            ])
            steps.extend(("signal", {"event_id": event}) for event in contract.get("required_events_before_b", []) if by_hook.get(event) == "atom_a_finish")
            steps.append(("move", {"arm": "LEFT", "pose": "left_home"}))
            return steps
        steps = []
        steps.extend(("wait_event", {"event_id": event}) for event in contract.get("required_events_before_b", []))
        steps.extend([
            ("acquire", {"arm": "RIGHT", "resource_id": resource}),
            ("move", {"arm": "RIGHT", "pose": "b_zone"}),
            ("move", {"arm": "RIGHT", "pose": "right_exit"}),
            ("release_resource", {"arm": "RIGHT", "resource_id": resource}),
        ])
        steps.extend(("clear_event", {"event_id": event}) for event in spec.get("events", {}))
        steps.append(("move", {"arm": "RIGHT", "pose": "right_home"}))
        return steps
    if kind in {"POSE_SUPPORT_DURING_ACTION", "CLEARANCE_BEFORE_ACTION"}:
        if atom == "A":
            steps = [
                ("acquire", {"arm": "LEFT", "resource_id": resource}),
                ("move", {"arm": "LEFT", "pose": contract["required_a_pose"]}),
            ]
            steps.extend(("signal", {"event_id": event}) for event in contract["a_ready_events"])
            steps.extend(("wait_event", {"event_id": event}) for event in [*contract["b_pre_events"], contract["commit_event"]])
            steps.extend([
                ("release_resource", {"arm": "LEFT", "resource_id": resource}),
                ("move", {"arm": "LEFT", "pose": "left_home"}),
            ])
            return steps
        steps = [("wait_event", {"event_id": event}) for event in contract["a_ready_events"]]
        steps.extend(("signal", {"event_id": event}) for event in contract["b_pre_events"])
        steps.extend([
            (contract["protected_action"], contract["protected_args"]),
            ("signal", {"event_id": contract["commit_event"]}),
            ("move", {"arm": "RIGHT", "pose": "right_home"}),
        ])
        return steps
    if kind == "RELEASE_BEFORE_COMMIT":
        if atom == "A":
            steps = [
                ("acquire", {"arm": "LEFT", "resource_id": resource}),
                ("move", {"arm": "LEFT", "pose": "a_zone"}),
                ("signal", {"event_id": contract["ready_event"]}),
            ]
            steps.extend(("wait_event", {"event_id": event}) for event in [*contract["required_prior_events"], contract["commit_event"]])
            steps.extend([
                ("release_resource", {"arm": "LEFT", "resource_id": resource}),
                ("move", {"arm": "LEFT", "pose": "left_home"}),
            ])
            return steps
        stage_hook = contract.get("stage_hook", "atom_b_dependency")
        steps = []
        if stage_hook == "atom_b_prepare": steps.extend(("signal", {"event_id": event}) for event in contract["required_prior_events"])
        steps.append(("wait_event", {"event_id": contract["ready_event"]}))
        if stage_hook == "atom_b_dependency": steps.extend(("signal", {"event_id": event}) for event in contract["required_prior_events"])
        steps.append(("move", {"arm": "RIGHT", "pose": "right_protected"}))
        if stage_hook == "atom_b_commit": steps.extend(("signal", {"event_id": event}) for event in contract["required_prior_events"])
        steps.append(("signal", {"event_id": contract["commit_event"]}))
        if stage_hook == "atom_b_finish": steps.extend(("signal", {"event_id": event}) for event in contract["required_prior_events"])
        steps.append(("move", {"arm": "RIGHT", "pose": "right_home"}))
        return steps
    if kind == "RECOVERY_OCCUPANCY":
        if atom == "A":
            return [
                ("acquire", {"arm": "LEFT", "resource_id": resource}),
                ("move", {"arm": "LEFT", "pose": "a_zone"}),
                ("move", {"arm": "LEFT", "pose": "left_exit"}),
                ("release_resource", {"arm": "LEFT", "resource_id": resource}),
                ("signal", {"event_id": contract["required_release_event"]}),
                ("move", {"arm": "LEFT", "pose": "left_home"}),
            ]
        return [
            ("wait_event", {"event_id": contract["required_release_event"]}),
            ("move", {"arm": "RIGHT", "pose": "b_zone"}),
            ("move", {"arm": "RIGHT", "pose": "right_exit"}),
            ("clear_event", {"event_id": contract["required_release_event"]}),
            ("move", {"arm": "RIGHT", "pose": "right_home"}),
        ]
    if kind == "QUARANTINE_OBJECT":
        if atom == "A": return [("acquire", {"arm": "LEFT", "resource_id": resource}), ("move", {"arm": "LEFT", "pose": "a_zone"}), ("signal", {"event_id": "quarantine_ready"}), ("signal", {"event_id": "quarantine_commit"}), ("release_resource", {"arm": "LEFT", "resource_id": resource}), ("move", {"arm": "LEFT", "pose": "left_home"})]
        return [("wait_event", {"event_id": "quarantine_commit"}), ("grasp", {"arm": "RIGHT", "object_id": "replacement_part"}), ("move", {"arm": "RIGHT", "pose": "recovered_bin"}), ("release", {"arm": "RIGHT", "object_id": "replacement_part", "support_zone": "recovered_bin"}), ("signal", {"event_id": "recovery_done"}), ("move", {"arm": "RIGHT", "pose": "right_home"})]
    if kind == "HOLD_ACK_BEFORE_RELEASE":
        if atom == "A": return [("acquire", {"arm": "LEFT", "resource_id": resource}), ("signal", {"event_id": "stop_started"}), ("signal", {"event_id": "hold_ack"}), ("release_resource", {"arm": "LEFT", "resource_id": resource}), ("move", {"arm": "LEFT", "pose": "left_home"})]
        payload = contract["release_args"]["resource_id"]
        return [("acquire", {"arm": "RIGHT", "resource_id": payload}), ("wait_event", {"event_id": "hold_ack"}), ("release_resource", {"arm": "RIGHT", "resource_id": payload}), ("signal", {"event_id": "payload_released"}), ("move", {"arm": "RIGHT", "pose": "right_home"})]
    if kind == "REROUTE_OBJECT_BEFORE_CLEANUP":
        if atom == "A": return [("acquire", {"arm": "LEFT", "resource_id": resource}), ("grasp", {"arm": "LEFT", "object_id": "rejected_part"}), ("signal", {"event_id": "reject_declared"}), ("release", {"arm": "LEFT", "object_id": "rejected_part", "support_zone": "reject_bin"}), ("signal", {"event_id": "reroute_commit"}), ("release_resource", {"arm": "LEFT", "resource_id": resource}), ("move", {"arm": "LEFT", "pose": "left_home"})]
        return [("wait_event", {"event_id": "reroute_commit"}), ("move", {"arm": "RIGHT", "pose": "original_route"}), ("signal", {"event_id": "cleanup_done"}), ("move", {"arm": "RIGHT", "pose": "right_home"})]
    if kind == "CLAMP_COMMIT_BEFORE_JAM_CLEAR":
        if atom == "A": return [("acquire", {"arm": "LEFT", "resource_id": resource}), ("signal", {"event_id": "clamp_active"}), ("signal", {"event_id": "safe_release_commit"}), ("release_resource", {"arm": "LEFT", "resource_id": resource}), ("move", {"arm": "LEFT", "pose": "left_home"})]
        return [("wait_event", {"event_id": "safe_release_commit"}), ("move", {"arm": "RIGHT", "pose": "right_protected"}), ("signal", {"event_id": "jam_cleared"}), ("move", {"arm": "RIGHT", "pose": "right_home"})]
    raise ValueError("unknown oracle kind: " + kind)


def dynamic_local_contract(capture: dict, spec: dict, atom: str) -> dict:
    steps = required_steps(spec, atom)
    passed = _subsequence(_events(capture), steps)
    return {
        "passed": passed,
        "required_step_count": len(steps),
        "reason": "required trusted-event subsequence observed" if passed else "required trusted-event subsequence missing",
    }
