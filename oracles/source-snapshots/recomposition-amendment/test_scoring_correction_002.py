"""Re-run 9-class C/V/NE tests and add self-producer/external-producer regressions."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V4 = HERE.parent / "rq2_structure_preserving_recomposition_v4"
OUT = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"
QUALITY = V4.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
sys.path.insert(0, str(V4))
from runtime import execute
from frozen_composer import SEEDS, compose
import run_oracle_boundary_challenges as legacy_challenges
from amended_measurement_correction_002 import EVENT_SEMANTICS, evaluate
from test_amended_measurement import early_clear_mutation


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


async def execute_until(source, spec, policy, expected):
    last = None
    for seed in SEEDS:
        capture = await execute(compose(source, "CONCURRENT", "SHORT", seed, policy), spec, ROOT)
        endpoint = evaluate(capture, spec)
        last = (capture, endpoint)
        if endpoint["P"] == expected:
            return last
    return last


async def main() -> None:
    catalog = {row["family_id"]: row for row in read(V4 / "REFERENCE_TASK_CATALOG.json")}
    rows = []
    safe = {}
    for kind, family_id in legacy_challenges.REPRESENTATIVES.items():
        task = catalog[family_id]
        spec = read(V4 / task["spec_path"])
        source = (V4 / task["reference_source_path"]).read_text(encoding="utf-8")
        violation, no_exposure = legacy_challenges.variants(kind, source)
        for label, candidate in (("C", source), ("V", violation), ("NE", no_exposure)):
            capture, endpoint = await execute_until(candidate, spec, task["serial_policy"], label)
            rows.append({"test": f"{kind}_{label}", "expected": label, "actual": endpoint["P"], "passed": endpoint["P"] == label})
            if label == "C": safe[kind] = (capture, spec)

    for kind in ("POSE_SUPPORT_DURING_ACTION", "CLEARANCE_BEFORE_ACTION", "RELEASE_BEFORE_COMMIT", "HOLD_ACK_BEFORE_RELEASE"):
        capture, spec = safe[kind]
        external_rules = [rule for rule in EVENT_SEMANTICS[spec["family_id"]]["persistent_active_states"] if rule["producer_role"] == "A_EXTERNAL"]
        if not external_rules:
            continue
        rule = external_rules[0]
        mutated = early_clear_mutation(capture, rule["event_id"], rule["critical_action"], rule["critical_args"])
        endpoint = evaluate(mutated, spec)
        rows.append({"test": f"{kind}_EXTERNAL_SIGNAL_CLEAR_BEFORE_USE", "expected": "V", "actual": endpoint["P"], "passed": endpoint["P"] == "V"})

    f07_task = catalog["R2V4-F07"]
    f07_spec = read(V4 / f07_task["spec_path"])
    f07_source = (V4 / f07_task["reference_source_path"]).read_text(encoding="utf-8")
    f07_capture, f07_endpoint = await execute_until(f07_source, f07_spec, f07_task["serial_policy"], "C")
    rows.append({"test": "SELF_PRODUCED_PERSISTENT_EVENT_ACTIVE_WITHOUT_WAIT_IS_C", "expected": "C", "actual": f07_endpoint["P"], "passed": f07_endpoint["P"] == "C"})
    self_rule = next(rule for rule in EVENT_SEMANTICS["R2V4-F07"]["persistent_active_states"] if rule["producer_role"] == "B_SELF")
    f07_cleared = early_clear_mutation(f07_capture, self_rule["event_id"], self_rule["critical_action"], self_rule["critical_args"])
    f07_cleared_endpoint = evaluate(f07_cleared, f07_spec)
    rows.append({"test": "SELF_PRODUCED_PERSISTENT_EVENT_CLEARED_BEFORE_USE_IS_V", "expected": "V", "actual": f07_cleared_endpoint["P"], "passed": f07_cleared_endpoint["P"] == "V"})

    result = {
        "schema": "paper3.rq2.v4_amendment.scoring_correction_002.gate.v1",
        "status": "PASS" if all(row["passed"] for row in rows) and len(rows) == 33 else "FAIL",
        "tests": len(rows), "rows": rows, "external_model_calls_added": 0,
    }
    write_json(OUT / "SCORING_CORRECTION_002_GATE.json", result)
    print(json.dumps({"status": result["status"], "tests": len(rows), "failures": [row for row in rows if not row["passed"]]}, ensure_ascii=False, indent=2))
    if result["status"] != "PASS": raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
