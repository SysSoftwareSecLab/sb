"""Independent observed-path oracle for the executable composition grammar."""
from collections import Counter
import ast

ROBOT_ACTIONS = {"move", "grasp", "release", "inspect", "refresh", "acquire", "release_resource", "wait_event", "signal", "clear_event", "hold", "safe_stop", "reset_failure", "set_mode", "transfer_authority"}


def action_multiset(capture):
    return dict(Counter(e["action"] for e in capture.get("trusted_events", []) if e.get("phase") == "complete" and e.get("action") in ROBOT_ACTIONS))


def intervals(capture, include_inspect=True):
    events = capture.get("trusted_events", [])
    starts = {e.get("operation_id"): e for e in events if e.get("phase") == "start" and e.get("operation_id") and e.get("args", {}).get("arm") in ["LEFT", "RIGHT"]}
    out = []
    for operation_id, start in starts.items():
        ends = [e for e in events if e.get("operation_id") == operation_id and e.get("phase") in ["complete", "fault", "timeout"]]
        if not ends or (not include_inspect and start.get("action") in ["inspect", "refresh"]):
            continue
        out.append((start["args"]["arm"], start["time"], ends[-1]["time"], start["action"], operation_id))
    return out


def cross_arm_overlap(capture, include_inspect=True):
    ints = intervals(capture, include_inspect)
    return sum(max(0.0, min(a[2], b[2]) - max(a[1], b[1])) for a in ints for b in ints if a[0] == "LEFT" and b[0] == "RIGHT")


def _between(events, first, last):
    return sum(e.get("phase") == "complete" and first < e["index"] < last and e.get("action") in ROBOT_ACTIONS for e in events)


def _pick(events, phase, action, occurrence=0, **args):
    found = [e for e in events if e.get("phase") == phase and e.get("action") == action and all(e.get("args", {}).get(k) == v for k, v in args.items())]
    return found[occurrence]


def focal_distance(task, capture):
    family = task["family"]
    ev = capture.get("trusted_events", [])
    if family == "D1_OBSERVATION":
        a = _pick(ev, "complete", "inspect", fact_id="quality")
        b = _pick(ev, "start", "grasp", 1, object_id="left_part")
    elif family == "D2_EVENT":
        a = _pick(ev, "complete", "signal", event_id="right_ready")
        b = _pick(ev, "start", "move", arm="LEFT", pose="left_target")
    elif family in ["D3_ATTR_FLAT", "D4_ATTR_NESTED"]:
        a = _pick(ev, "complete", "acquire", 1, resource_id="tool")
        b = _pick(ev, "start", "release_resource", 1, resource_id="tool")
    elif family == "D5_FRESHNESS":
        a = _pick(ev, "complete", "inspect", fact_id="route")
        b = _pick(ev, "start", "grasp", object_id="left_part")
    elif family == "D6_RESOURCE_SPAN":
        a = _pick(ev, "complete", "acquire", resource_id="fixture")
        b = _pick(ev, "start", "release_resource", resource_id="fixture")
    elif family == "D7_BUFFER_PREFETCH":
        a = _pick(ev, "complete", "grasp", object_id="part_1")
        b = _pick(ev, "start", "move", arm="LEFT", pose="buffer_1")
    elif family == "D8_ALLOCATION":
        a = _pick(ev, "complete", "inspect", arm="LEFT", fact_id="allocation")
        b = _pick(ev, "start", "grasp", object_id="shared_part")
    else:
        raise KeyError(family)
    return _between(ev, a["index"], b["index"])


def source_features(source):
    tree = ast.parse(source)
    top = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "run_task")
    defs = {n.name: n for n in ast.walk(top) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    reached, pending = set(), ["run_task"]
    while pending:
        name = pending.pop()
        if name in reached or name not in defs:
            continue
        reached.add(name)
        pending.extend(n.func.id for n in ast.walk(defs[name]) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in defs)
    calls = {name: {n.func.id for n in ast.walk(defs[name]) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in defs} for name in reached}
    direct = {name: sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "gather" for n in ast.walk(defs[name])) for name in reached}
    def reaches(name, seen=None):
        seen = set() if seen is None else seen
        if name in seen:
            return False
        seen.add(name)
        return direct.get(name, 0) > 0 or any(reaches(x, seen.copy()) for x in calls.get(name, set()))
    def compound(node):
        if any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "gather" for x in ast.walk(node)):
            return True
        return any(reaches(x.func.id) for x in ast.walk(node) if isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id in defs)
    nodes = [n for name in reached for n in ast.walk(defs[name])]
    return {
        "gather_nodes": sum(direct.values()),
        "loop_calls_gather_interprocedural": any(isinstance(n, ast.For) and compound(n) for n in nodes),
        "branch_calls_gather_interprocedural": any(isinstance(n, ast.If) and compound(n) for n in nodes),
    }


def evaluate(task, spec, source, capture, reference_metrics):
    complete = bool(capture.get("execution_lifecycle_complete"))
    rows = []
    def add(name, ok, value, expected):
        rows.append({"obligation": name, "label": "C" if ok else "V" if complete else "U", "observed": value, "expected": expected})
    family, axis, level = task["family"], task["axis"], task["level"]
    try:
        if axis == "CONCURRENCY":
            metric = cross_arm_overlap(capture, include_inspect=True)
            lo, hi = reference_metrics["serial_overlap"], reference_metrics["concurrent_overlap"]
            threshold = (lo + hi) / 2
            add("COMPOSITION_CONCURRENCY", metric <= threshold if level == "SERIAL" else metric > threshold, metric, {"level": level, "threshold": threshold, "reference_serial": lo, "reference_concurrent": hi})
        else:
            metric = focal_distance(task, capture)
            lo, hi = reference_metrics["short_distance"], reference_metrics["long_distance"]
            threshold = (lo + hi) / 2
            add("LONG_RANGE_DEPENDENCY", metric <= threshold if level == "SHORT" else metric > threshold, metric, {"level": level, "threshold": threshold, "reference_short": lo, "reference_long": hi})
    except (KeyError, IndexError, StopIteration):
        add("COMPOSITION_CONCURRENCY" if axis == "CONCURRENCY" else "LONG_RANGE_DEPENDENCY", False, "FOCAL_EVENTS_MISSING", level)

    if family in ["C7_ATTR_FLAT", "C8_ATTR_NESTED", "D3_ATTR_FLAT", "D4_ATTR_NESTED"]:
        events = capture.get("trusted_events", [])
        try:
            clear = _pick(events, "complete", "clear_event", event_id="empty_0")
            left = _pick(events, "complete", "inspect", fact_id="line_clear")
            right = _pick(events, "complete", "inspect", fact_id="receiver_ready")
            entry = _pick(events, "start", "move", arm="LEFT", pose="buffer_1")
            tool_acq = _pick(events, "complete", "acquire", 1, resource_id="tool")
            source1 = _pick(events, "start", "move", arm="LEFT", pose="source_1")
            order_ok = clear["index"] < left["index"] < entry["index"] and clear["index"] < right["index"] < entry["index"]
            if family.startswith("C") or level == "LONG":
                tool_ok = tool_acq["index"] < source1["index"]
            else:
                tool_ok = tool_acq["index"] > max(left["index"], right["index"])
            add("ATTRIBUTE_COMBINATION", order_ok and tool_ok, {"clear": clear["index"], "left_check": left["index"], "right_check": right["index"], "tool_acquire": tool_acq["index"], "source1": source1["index"], "buffer1": entry["index"]}, "empty receipt -> two checks -> buffer entry, with assigned tool span")
        except (KeyError, IndexError):
            add("ATTRIBUTE_COMBINATION", False, "REQUIRED_EVENTS_MISSING", "empty receipt, two checks, tool scope")
        sf = source_features(source)
        nested = family in ["C8_ATTR_NESTED", "D4_ATTR_NESTED"]
        add("CONTROL_FLOW_HOLDOUT", sf["loop_calls_gather_interprocedural"] == nested and sf["branch_calls_gather_interprocedural"] == nested, sf, {"nested_for_if_join": nested})
    return {"rows": rows, "summary": {x["obligation"]: x["label"] for x in rows}, "scope": "Observed finite path plus reachable source control flow; independent of model judge and human labels"}

