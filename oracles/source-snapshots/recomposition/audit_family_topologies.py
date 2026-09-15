"""Audit implementation-level safety topology, without task prose or names."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent


def read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def literal(node: ast.AST) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return "<dynamic>"


def robot_calls(source: str) -> dict[str, list[tuple[str, list[object]]]]:
    tree = ast.parse(source)
    output = {}
    for function in (node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)):
        calls = []
        for statement in function.body:
            call = statement.value if isinstance(statement, (ast.Expr, ast.Assign)) else None
            if isinstance(call, ast.Await):
                call = call.value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "robot":
                calls.append((call.func.attr, [literal(arg) for arg in call.args]))
        output[function.name] = calls
    return output


def family_signature(task: dict) -> tuple[dict, set[str]]:
    spec = read(HERE / task["spec_path"])
    contract = spec["rq2_direct_p_contract"]
    calls = robot_calls((HERE / task["reference_source_path"]).read_text(encoding="utf-8"))
    primary_resource = next(iter(spec["resources"]))
    event_roles = defaultdict(lambda: {"signal": [], "wait": [], "clear": []})
    for hook, rows in calls.items():
        for method, args in rows:
            if method in {"signal", "wait_event", "clear_event"} and args and args[0] in spec["events"]:
                event_roles[args[0]][{"signal": "signal", "wait_event": "wait", "clear_event": "clear"}[method]].append(hook)
    event_role = {
        event: (tuple(value["signal"]), tuple(value["wait"]), tuple(value["clear"]))
        for event, value in event_roles.items()
    }
    ordered_events = sorted(event_role, key=lambda event: (event_role[event], event))
    event_alias = {event: f"event_role_{index}:{event_role[event]}" for index, event in enumerate(ordered_events)}
    object_alias = {}
    if "quarantined_object" in contract:
        object_alias[contract["quarantined_object"]] = "quarantined_object"
        object_alias[contract["replacement_object"]] = "replacement_object"
    if "object_id" in contract:
        object_alias[contract["object_id"]] = "rerouted_object"

    def normalize(method: str, args: list[object]) -> tuple:
        normalized = []
        for value in args:
            if value in event_alias:
                normalized.append(event_alias[value])
            elif value in spec["resources"]:
                normalized.append("primary_resource" if value == primary_resource else "secondary_resource")
            elif value in object_alias:
                normalized.append(object_alias[value])
            elif value in spec["world"]["pose_coordinates_m"]:
                normalized.append("pose:" + str(value))
            elif isinstance(value, str) and value.startswith("context_fact_"):
                normalized.append("context_fact")
            elif isinstance(value, str) and value.startswith("neutral_fact_"):
                normalized.append("neutral_fact")
            elif value in {"LEFT", "RIGHT"}:
                normalized.append(value)
            elif isinstance(value, (int, float)):
                normalized.append("duration")
            else:
                normalized.append(type(value).__name__)
        return (method, *normalized)

    hooks = {}
    features = {"oracle:" + contract["oracle_kind"]}
    for hook, rows in calls.items():
        normalized_rows = [normalize(method, args) for method, args in rows if not (method == "inspect" and args and isinstance(args[-1], str) and args[-1].startswith("context_fact_"))]
        hooks[hook] = normalized_rows
        for index, row in enumerate(normalized_rows):
            features.add(f"hook:{hook}:{index}:{row}")
    predicate = {
        key: value
        for key, value in contract.items()
        if key not in {"mechanism"}
    }
    # Contract values are implementation fields, not the free-text task story.
    canonical = {"oracle_kind": contract["oracle_kind"], "hooks": hooks, "event_graph": sorted(event_role.values()), "predicate_keys": sorted(predicate)}
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return canonical, features


def main() -> None:
    catalog = read(HERE / "REFERENCE_TASK_CATALOG.json")
    rows = []
    feature_sets = {}
    for task in catalog:
        canonical, features = family_signature(task)
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        rows.append({"family_id": task["family_id"], "oracle_kind": task["oracle_kind"], "implementation_topology_sha256": digest, "canonical": canonical})
        feature_sets[task["family_id"]] = features
    pairs = []
    for index, left in enumerate(sorted(feature_sets)):
        for right in sorted(feature_sets)[index + 1:]:
            union = feature_sets[left] | feature_sets[right]
            overlap = len(feature_sets[left] & feature_sets[right]) / len(union) if union else 1.0
            pairs.append({"left": left, "right": right, "jaccard": overlap})
    unique = len({row["implementation_topology_sha256"] for row in rows})
    result = {
        "schema": "paper3.rq2.family_implementation_topology_audit.v1",
        "status": "PASS" if unique == 24 else "FAIL_NONINDEPENDENT_IMPLEMENTATION_TOPOLOGIES",
        "scenario_families": 24,
        "unique_implementation_topologies": unique,
        "oracle_classes": len({row["oracle_kind"] for row in rows}),
        "unit_claim": "24 fixed scenario families; not 24 independent safety mechanisms",
        "rows": rows,
        "pairwise_overlap": pairs,
        "maximum_pairwise_jaccard": max((row["jaccard"] for row in pairs), default=0.0),
        "external_model_calls": 0,
    }
    write_json(HERE / "FAMILY_TOPOLOGY_AUDIT.json", result)
    print(json.dumps({key: result[key] for key in ("status", "scenario_families", "unique_implementation_topologies", "oracle_classes", "maximum_pairwise_jaccard")}, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
