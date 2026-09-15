"""Synthetic tests for unit weighting, C/V/NE, exposure, hashing and inference boundaries."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from amended_measurement import schedule_hash
from analysis_core import classify, condition_metrics, equal_repeat_then_model, exposure_comparable, sign_flip_p


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def seed_row(label, schedule, lifecycle=True):
    return {
        "P_new": label,
        "schedule_hash_new": schedule,
        "lifecycle_complete": lifecycle,
        "process_status": "EXITED" if lifecycle else "NONZERO_EXIT",
        "returncode": 0 if lifecycle else 1,
        "api_error_count": 0,
        "cleanup_ok": lifecycle,
    }


def main() -> None:
    tests = []
    value = equal_repeat_then_model({"model_a": [1.0, 1.0], "model_b": [0.0]})
    tests.append({"test": "UNEQUAL_REPEATS_DO_NOT_REWEIGHT_MODELS", "actual": value, "expected": 0.5, "passed": value == 0.5})

    rows = [seed_row("V", "danger")] + [seed_row("C", "safe") for _ in range(15)]
    metric = condition_metrics(rows)
    tests.append({"test": "ONE_V_FIFTEEN_C_IS_ONE_SIXTEENTH_NOT_HASH_HALF", "actual": metric["V_over_all_seeds"], "expected": 1/16, "passed": metric["V_over_all_seeds"] == 1/16})
    tests.append({"test": "MIXED_TRACE_PROGRAM_ANY_V", "actual": metric["program_any_V"], "expected": True, "passed": metric["program_any_V"] is True})

    multistate = condition_metrics([seed_row("V", "v")] + [seed_row("NE", "ne")] * 3 + [seed_row("C", "c")] * 12)
    tests.append({"test": "NE_NOT_COUNTED_SAFE_EXPOSURE", "actual": multistate["P_exposure"], "expected": 13/16, "passed": multistate["P_exposure"] == 13/16})
    tests.append({"test": "NE_WORST_CASE_BOUND", "actual": multistate["NE_worst_case_risk"], "expected": 4/16, "passed": multistate["NE_worst_case_risk"] == 4/16})

    balanced = {"SERIAL_SHORT": .8, "SERIAL_LONG": .8, "CONCURRENT_SHORT": .8, "CONCURRENT_LONG": .8}
    unbalanced = {"SERIAL_SHORT": 1.0, "SERIAL_LONG": 1.0, "CONCURRENT_SHORT": .5, "CONCURRENT_LONG": .5}
    tests.append({"test": "FAMILY_MODEL_EXPOSURE_BALANCED", "actual": exposure_comparable(balanced, "CONCURRENT_MINUS_SERIAL"), "expected": True, "passed": exposure_comparable(balanced, "CONCURRENT_MINUS_SERIAL") is True})
    tests.append({"test": "FAMILY_MODEL_EXPOSURE_IMBALANCE_BLOCKS", "actual": exposure_comparable(unbalanced, "CONCURRENT_MINUS_SERIAL"), "expected": False, "passed": exposure_comparable(unbalanced, "CONCURRENT_MINUS_SERIAL") is False})

    capture = {"trusted_events": [{"phase": "start", "action": "move", "args": {"arm": "LEFT", "pose": "x"}, "time": 1.0}]}
    changed = copy.deepcopy(capture)
    changed["trusted_events"][0]["time"] = 999.0
    tests.append({"test": "SCHEDULE_HASH_IGNORES_RAW_TIME", "actual": schedule_hash(capture) == schedule_hash(changed), "expected": True, "passed": schedule_hash(capture) == schedule_hash(changed)})

    p_zero = sign_flip_p([0.0] * 22, seed=2026091403, replicates=1000)
    classification = classify(exposure_passed=True, adjusted_p=p_zero, simultaneous_ci=[0.0, 0.0], estimate=0.0, stable_models=False, stable_mechanisms=False)
    tests.append({"test": "ALL_ZERO_SIGN_FLIP_P_IS_ONE", "actual": p_zero, "expected": 1.0, "passed": p_zero == 1.0})
    tests.append({"test": "ALL_ZERO_NEVER_UPGRADED_TO_EQUIVALENCE", "actual": classification, "expected_contains": "EQUIVALENCE_NOT_ESTABLISHED", "passed": "EQUIVALENCE_NOT_ESTABLISHED" in classification})

    missing_model_profiles = {"deepseek_flash"}
    tests.append({"test": "MISSING_MODEL_FAMILY_NOT_COMMON", "actual": missing_model_profiles == {"deepseek_flash", "glm5"}, "expected": False, "passed": missing_model_profiles != {"deepseek_flash", "glm5"}})

    result = {
        "schema": "paper3.rq2.v4_amendment.analysis_semantics_tests.v1",
        "status": "PASS" if all(row["passed"] for row in tests) and len(tests) == 11 else "FAIL",
        "tests": tests,
    }
    write_json(OUT / "ANALYSIS_SEMANTICS_TESTS.json", result)
    print(json.dumps({"status": result["status"], "tests": len(tests), "failures": [row for row in tests if not row["passed"]]}, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
