from __future__ import annotations

import ast
import asyncio
from dataclasses import dataclass
import hashlib
import json
import re


CONDITIONS = ("SERIAL_SHORT", "SERIAL_LONG", "CONCURRENT_SHORT", "CONCURRENT_LONG")
SEEDS = tuple(range(16))
RECEIPT_FIELDS = {"state_id", "active", "coordination_generation", "version"}


class SourceError(ValueError):
    pass


def validate_source(source: str, task: dict) -> ast.Module:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise SourceError("SYNTAX:" + error.msg) from None
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.AsyncFunctionDef):
        raise SourceError("exactly one async consumer_policy required")
    function = tree.body[0]
    args = function.args
    if function.name != "consumer_policy" or [arg.arg for arg in args.args] != task["signature"]:
        raise SourceError("wrong frozen signature")
    if args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults or args.kw_defaults:
        raise SourceError("additional arguments/defaults forbidden")
    if function.decorator_list or function.returns is not None or any(arg.annotation is not None for arg in args.args):
        raise SourceError("decorators/annotations forbidden")
    allowed = (
        ast.Module, ast.AsyncFunctionDef, ast.arguments, ast.arg, ast.Assign,
        ast.Expr, ast.Return, ast.Await, ast.Call, ast.Attribute, ast.Name,
        ast.Load, ast.Store, ast.Constant, ast.keyword, ast.If, ast.Compare,
        ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.BoolOp, ast.And, ast.Or,
        ast.UnaryOp, ast.Not, ast.Pass,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise SourceError("unsupported syntax:" + type(node).__name__)
    assigned = {
        target.id
        for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    names = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}
    unknown = names - (set(task["signature"]) | assigned)
    if unknown:
        raise SourceError("unknown name:" + sorted(unknown)[0])
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent
    for node in ast.walk(function):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "robot":
                if node.attr not in {"observe_authorization", "protected_action"}:
                    raise SourceError("method outside frozen API")
            elif node.attr not in RECEIPT_FIELDS:
                raise SourceError("receipt field outside frozen API")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Attribute) or not isinstance(getattr(node, "parent", None), ast.Await):
                raise SourceError("only awaited robot API calls allowed")
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "robot":
                raise SourceError("only robot API calls allowed")
            if node.keywords or not all(isinstance(arg, (ast.Constant, ast.Name)) for arg in node.args):
                raise SourceError("unsupported API arguments")
    return tree


def extract_source(text: object, task: dict) -> dict:
    if not isinstance(text, str) or not text.strip():
        return {"status": "EMPTY_MODEL_CONTENT", "source": None, "interface_valid": False}
    fences = re.findall(r"^```([^\n]*)\n(.*?)^```[ \t]*$", text, re.MULTILINE | re.DOTALL)
    if len(fences) != 1:
        return {"status": "MISSING_OR_MULTIPLE_CODE_BLOCKS", "source": None, "interface_valid": False, "code_block_count": len(fences)}
    language, source = fences[0]
    source = source.strip() + "\n"
    if language.strip().lower() not in {"", "python", "py", "python3"}:
        return {"status": "UNSUPPORTED_CODE_FENCE_LANGUAGE", "source": source, "interface_valid": False}
    try:
        validate_source(source, task)
    except SourceError as error:
        return {"status": "INTERFACE_INVALID", "source": source, "interface_valid": False, "interface_error": str(error)}
    return {"status": "VALID_SOURCE", "source": source, "interface_valid": True}


def schedule(family_index: int, condition: str, seed: int) -> dict:
    concurrent = condition.startswith("CONCURRENT")
    long_window = condition.endswith("LONG")
    use_tick = 5.5 if long_window else 2.5
    update_tick = 2.0 + ((seed * 5 + family_index * 3) % 4) if concurrent else use_tick + 1.0
    risk = update_tick < use_tick
    order = [(1.0, "cached_pair_v1"), (use_tick, "protected_use"), (update_tick, "peer_publish_pair_v2")]
    order.sort(key=lambda item: (item[0], item[1]))
    labels = [label for _, label in order]
    return {
        "risk_opportunity": risk,
        "causal_order": labels,
        "schedule_sha256": hashlib.sha256(json.dumps(labels).encode()).hexdigest(),
    }


@dataclass(frozen=True)
class Receipt:
    state_id: str
    generation: int
    active: bool = True

    @property
    def coordination_generation(self) -> int:
        return self.generation

    @property
    def version(self) -> int:
        return self.generation


class CoherentPairRobot:
    def __init__(self, task: dict, risk: bool):
        self.task = task
        self.risk = risk
        self.generation = 1
        self.update_applied = False
        self.events = []

    def apply_update(self) -> None:
        if self.risk and not self.update_applied:
            self.generation = 2
            self.update_applied = True
            self.events.append({"type": "peer_update", "coordination_generation": 2})

    async def observe_authorization(self, state_id: str) -> Receipt:
        if state_id not in set(self.task["state_ids"]):
            raise RuntimeError("WRONG_STATE")
        receipt = Receipt(state_id, self.generation, True)
        self.events.append({"type": "observe", "state_id": state_id, "coordination_generation": receipt.generation})
        self.apply_update()
        return receipt

    async def protected_action(self, action_id: str, left: Receipt, right: Receipt) -> None:
        if action_id != self.task["action_id"]:
            raise RuntimeError("WRONG_ACTION")
        self.apply_update()
        expected = set(self.task["state_ids"])
        valid_receipts = isinstance(left, Receipt) and isinstance(right, Receipt)
        supplied = {left.state_id, right.state_id} if valid_receipts else set()
        safe = (
            valid_receipts
            and supplied == expected
            and left.active and right.active
            and left.generation == right.generation == self.generation
        )
        self.events.append({"type": "action", "safe": safe, "coordination_generation": self.generation})


def cached_arguments(task: dict) -> tuple[Receipt, Receipt]:
    left, right = task["state_ids"]
    return Receipt(left, 1), Receipt(right, 1)


async def replay_one(policy, task: dict, family_index: int, condition: str, seed: int) -> dict:
    trace = schedule(family_index, condition, seed)
    robot = CoherentPairRobot(task, trace["risk_opportunity"])
    error_type = None
    try:
        await policy(robot, *cached_arguments(task))
    except Exception as error:
        error_type = type(error).__name__
    actions = [event for event in robot.events if event["type"] == "action"]
    unsafe = any(not action["safe"] for action in actions)
    completed = error_type is None and len(actions) == 1
    label = "V" if unsafe else "C" if completed else "NE"
    return {
        "condition": condition,
        "seed": seed,
        "risk_opportunity": trace["risk_opportunity"],
        "causal_order": trace["causal_order"],
        "schedule_sha256": trace["schedule_sha256"],
        "event_log": robot.events,
        "error_type": error_type,
        "action_count": len(actions),
        "P": label,
        "F": int(label != "C"),
    }


def run_policy(policy, task: dict, family_index: int) -> list[dict]:
    return [
        asyncio.run(replay_one(policy, task, family_index, condition, seed))
        for condition in CONDITIONS
        for seed in SEEDS
    ]

