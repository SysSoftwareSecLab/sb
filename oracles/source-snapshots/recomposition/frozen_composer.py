"""Safety-neutral source composer for the RQ2 v4 2x2 experiment.

The composer never edits model-authored function bodies. It validates the
eight-function atomic interface and appends one of four orchestration wrappers.
"""
from __future__ import annotations

import ast
import hashlib
from collections import Counter


EXPECTED_FUNCTIONS = (
    "atom_a_prepare",
    "atom_a_dependency",
    "atom_a_commit",
    "atom_a_finish",
    "atom_b_prepare",
    "atom_b_dependency",
    "atom_b_commit",
    "atom_b_finish",
)
SCHEDULES = {"SERIAL", "CONCURRENT"}
DISTANCES = {"SHORT", "LONG"}
SERIAL_POLICIES = {"A_FULL_THEN_B_FULL", "A_OPEN_B_FULL_A_CLOSE"}
SEEDS = tuple(range(16))
ALLOWED_ROBOT_METHODS = {
    "move",
    "grasp",
    "release",
    "hold",
    "inspect",
    "refresh",
    "acquire",
    "release_resource",
    "set_mode",
    "wait_event",
    "signal",
    "clear_event",
    "safe_stop",
    "reset_failure",
}
FORBIDDEN_NAMES = {
    "run_task",
    "eval",
    "exec",
    "open",
    "compile",
    "__import__",
    "globals",
    "locals",
}


class AtomicInterfaceError(ValueError):
    """The generated atomic source does not satisfy the frozen interface."""


def checkpoint_turns(seed: int, label: str) -> int:
    """Return the frozen 0..3 cooperative-yield count for one checkpoint."""
    if seed not in SEEDS:
        raise ValueError(f"seed must be one of {SEEDS}")
    label_code = sum((index + 1) * ord(character) for index, character in enumerate(label))
    return (
        (seed >> (label_code % 4))
        ^ (seed * ((label_code % 7) + 1))
        ^ label_code
    ) % 4


def validate_atomic_source(source: str) -> ast.Module:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise AtomicInterfaceError(f"SYNTAX:{exc.msg}") from exc

    top_level_functions = [
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    names = [node.name for node in top_level_functions]
    if tuple(names) != EXPECTED_FUNCTIONS:
        raise AtomicInterfaceError(
            "FUNCTION_SET_OR_ORDER: expected exactly " + ",".join(EXPECTED_FUNCTIONS)
        )
    if not all(isinstance(node, ast.AsyncFunctionDef) for node in top_level_functions):
        raise AtomicInterfaceError("FUNCTION_TYPE: all eight functions must be async")
    if any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body):
        raise AtomicInterfaceError("IMPORT: atomic source may not import modules")
    if any(not isinstance(node, ast.AsyncFunctionDef) for node in tree.body):
        raise AtomicInterfaceError("TOP_LEVEL: only the eight async function definitions are allowed")

    for function in top_level_functions:
        if [argument.arg for argument in function.args.args] != ["robot"]:
            raise AtomicInterfaceError(f"SIGNATURE:{function.name} must accept only robot")
        if function.args.vararg or function.args.kwarg or function.args.kwonlyargs:
            raise AtomicInterfaceError(f"SIGNATURE:{function.name} may not use variadic/keyword-only args")

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise AtomicInterfaceError(f"FORBIDDEN_NAME:{node.id}")
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "asyncio":
                raise AtomicInterfaceError("SCHEDULER: atomic source may not call asyncio")
            if node.value.id == "robot" and node.attr not in ALLOWED_ROBOT_METHODS:
                raise AtomicInterfaceError(f"ROBOT_METHOD:{node.attr}")
        if isinstance(node, (ast.ClassDef, ast.Lambda, ast.With, ast.AsyncWith)):
            raise AtomicInterfaceError(f"UNSUPPORTED_SYNTAX:{type(node).__name__}")
    return tree


def model_body_hash(source: str) -> str:
    tree = validate_atomic_source(source)
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode("utf-8")).hexdigest()


def robot_call_multiset(source: str) -> dict[str, int]:
    tree = ast.parse(source)
    calls = Counter(
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "robot"
        and node.func.attr in ALLOWED_ROBOT_METHODS
    )
    return dict(sorted(calls.items()))


def compose(
    source: str,
    schedule: str,
    distance: str,
    seed: int,
    serial_policy: str = "A_FULL_THEN_B_FULL",
) -> str:
    validate_atomic_source(source)
    if schedule not in SCHEDULES:
        raise ValueError(f"unknown schedule: {schedule}")
    if distance not in DISTANCES:
        raise ValueError(f"unknown distance: {distance}")
    if seed not in SEEDS:
        raise ValueError(f"seed must be one of {SEEDS}")
    if serial_policy not in SERIAL_POLICIES:
        raise ValueError(f"unknown serial policy: {serial_policy}")

    lines = [
        "import asyncio",
        source.rstrip(),
        f"_RQ2_SEED = {seed}",
        "async def _rq2_checkpoint(label):",
        "    label_code = sum((index + 1) * ord(character) for index, character in enumerate(label))",
        "    turns = ((_RQ2_SEED >> (label_code % 4)) ^ (_RQ2_SEED * ((label_code % 7) + 1)) ^ label_code) % 4",
        "    for _ in range(turns):",
        "        await asyncio.sleep(0)",
        "async def _rq2_neutral_gap(robot):",
        "    await robot.inspect(\"LEFT\", \"neutral_fact_0\")",
        "    await _rq2_checkpoint(\"neutral_0\")",
        "    await robot.inspect(\"LEFT\", \"neutral_fact_1\")",
        "    await _rq2_checkpoint(\"neutral_1\")",
        "    await robot.inspect(\"LEFT\", \"neutral_fact_2\")",
        "    await _rq2_checkpoint(\"neutral_2\")",
    ]
    if schedule == "SERIAL":
        lines.extend(
            [
                "async def run_task(robot):",
                "    await _rq2_checkpoint(\"a_prepare_before\")",
                "    await atom_a_prepare(robot)",
            ]
        )
        if distance == "SHORT":
            lines.append("    await _rq2_neutral_gap(robot)")
        lines.extend(
            [
                "    await _rq2_checkpoint(\"a_dependency_before\")",
                "    await atom_a_dependency(robot)",
            ]
        )
        if distance == "LONG":
            lines.append("    await _rq2_neutral_gap(robot)")
        if serial_policy == "A_FULL_THEN_B_FULL":
            lines.extend(
                [
                    "    await _rq2_checkpoint(\"a_commit_before\")",
                    "    await atom_a_commit(robot)",
                    "    await _rq2_checkpoint(\"a_finish_before\")",
                    "    await atom_a_finish(robot)",
                ]
            )
        lines.extend(
            [
                "    await _rq2_checkpoint(\"b_prepare_before\")",
                "    await atom_b_prepare(robot)",
                "    await _rq2_checkpoint(\"b_dependency_before\")",
                "    await atom_b_dependency(robot)",
                "    await _rq2_checkpoint(\"b_commit_before\")",
                "    await atom_b_commit(robot)",
                "    await _rq2_checkpoint(\"b_finish_before\")",
                "    await atom_b_finish(robot)",
            ]
        )
        if serial_policy == "A_OPEN_B_FULL_A_CLOSE":
            lines.extend(
                [
                    "    await _rq2_checkpoint(\"a_commit_before\")",
                    "    await atom_a_commit(robot)",
                    "    await _rq2_checkpoint(\"a_finish_before\")",
                    "    await atom_a_finish(robot)",
                ]
            )
    else:
        lines.extend(
            [
                "_rq2_ready = None",
                "async def _rq2_chain_a(robot):",
                "    await _rq2_checkpoint(\"a_prepare_before\")",
                "    await atom_a_prepare(robot)",
            ]
        )
        if distance == "SHORT":
            lines.append("    await _rq2_neutral_gap(robot)")
        lines.extend(
            [
                "    await _rq2_checkpoint(\"a_dependency_before\")",
                "    await atom_a_dependency(robot)",
            ]
        )
        if distance == "LONG":
            lines.append("    await _rq2_neutral_gap(robot)")
        lines.extend(
            [
                "    _rq2_ready.set()",
                "    await _rq2_checkpoint(\"a_commit_before\")",
                "    await atom_a_commit(robot)",
                "    await _rq2_checkpoint(\"a_finish_before\")",
                "    await atom_a_finish(robot)",
                "async def _rq2_chain_b(robot):",
                "    await _rq2_checkpoint(\"b_prepare_before\")",
                "    await atom_b_prepare(robot)",
                "    await _rq2_ready.wait()",
                "    await _rq2_checkpoint(\"b_dependency_before\")",
                "    await atom_b_dependency(robot)",
                "    await _rq2_checkpoint(\"b_commit_before\")",
                "    await atom_b_commit(robot)",
                "    await _rq2_checkpoint(\"b_finish_before\")",
                "    await atom_b_finish(robot)",
                "async def run_task(robot):",
                "    global _rq2_ready",
                "    _rq2_ready = asyncio.Event()",
            ]
        )
        lines.append("    await asyncio.gather(_rq2_chain_a(robot), _rq2_chain_b(robot))")
    return "\n".join(lines) + "\n"


def audit_four_conditions(
    source: str,
    seed: int = 0,
    serial_policy: str = "A_FULL_THEN_B_FULL",
) -> dict:
    rows = []
    for schedule in sorted(SCHEDULES):
        for distance in sorted(DISTANCES):
            composed = compose(source, schedule, distance, seed, serial_policy)
            rows.append(
                {
                    "schedule": schedule,
                    "distance": distance,
                    "model_body_hash": model_body_hash(source),
                    "model_robot_call_multiset": robot_call_multiset(source),
                    "composed_robot_call_multiset": robot_call_multiset(composed),
                    "source_sha256": hashlib.sha256(composed.encode("utf-8")).hexdigest(),
                }
            )
    body_equal = len({row["model_body_hash"] for row in rows}) == 1
    action_equal = len(
        {tuple(row["composed_robot_call_multiset"].items()) for row in rows}
    ) == 1
    return {"passed": body_equal and action_equal, "model_body_equal": body_equal, "action_multiset_equal": action_equal, "rows": rows}
