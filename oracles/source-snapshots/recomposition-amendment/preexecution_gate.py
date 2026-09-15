"""Executable hard gate before completing any amendment trace."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V4 = HERE.parent / "rq2_structure_preserving_recomposition_v4"
OUT = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run(script: str) -> None:
    subprocess.run([sys.executable, script], cwd=HERE, check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


def main() -> None:
    # These invoke the same amended scoring and aggregation functions used in
    # execution/analysis; they are not file-existence checks.
    run("build_measurement_contracts.py")
    run("requalify_atomic.py")
    run("test_amended_measurement.py")
    run("test_analysis_semantics.py")
    run("power_22.py")

    parent_freeze = read(V4 / "SCIENTIFIC_FREEZE.json")
    parent_hashes_ok = all(sha(ROOT / item["path"]) == item["sha256"] for item in parent_freeze["files"])
    ledger = read(OUT / "EXPOSURE_LEDGER.json")
    ledger_hashes_ok = all(sha(ROOT / item["path"]) == item["sha256"] for item in ledger["artifacts"])
    qualification = read(OUT / "AMENDED_ATOMIC_QUALIFICATION.json")
    measurement = read(OUT / "MEASUREMENT_GATE.json")
    semantics = read(OUT / "ANALYSIS_SEMANTICS_TESTS.json")
    event_semantics = read(HERE / "EVENT_SEMANTICS.json")
    local_goals = read(HERE / "ATOMIC_LOCAL_GOALS.json")
    power = read(HERE / "POWER_22_FAMILY.json")
    p10 = next(row["positive_power_bonferroni_lower_bound"] for row in power["scenarios"] if row["true_effect"] == 0.10)
    eq0 = next(row["equivalence_power_bonferroni_tost"] for row in power["scenarios"] if row["true_effect"] == 0.0)
    checks = {
        "parent_v4_freeze_unchanged": parent_hashes_ok,
        "all_pre_amendment_exposed_artifacts_hash_match": ledger_hashes_ok,
        "exposure_ledger_5248_complete_rows": ledger["result_count"] == 5248 and ledger["complete_64_result_slots"] == 82,
        "measurement_gate_actual_33_tests_pass": measurement["status"] == "PASS" and measurement["tests"] == 33,
        "analysis_semantics_actual_11_tests_pass": semantics["status"] == "PASS" and len(semantics["tests"]) == 11,
        "atomic_qualification_exactly_90": qualification["status"] == "PASS_EXPECTED_90" and qualification["eligible_slots"] == 90,
        "common_family_exactly_22": qualification["common_family_count"] == 22,
        "mechanism_distribution_6_6_6_4": sorted(qualification["mechanism_common_family_counts"].values()) == [4, 6, 6, 6],
        "24_family_event_semantics": len(event_semantics["families"]) == 24,
        "48_atomic_local_goals": len(local_goals["families"]) == 24 and all("atom_A" in row and "atom_B" in row for row in local_goals["families"]),
        "schedule_hash_time_negative_test_pass": next(row for row in semantics["tests"] if row["test"] == "SCHEDULE_HASH_IGNORES_RAW_TIME")["passed"],
        "NE_not_safe_negative_test_pass": next(row for row in semantics["tests"] if row["test"] == "NE_NOT_COUNTED_SAFE_EXPOSURE")["passed"],
        "hash_weighting_negative_test_pass": next(row for row in semantics["tests"] if row["test"] == "ONE_V_FIFTEEN_C_IS_ONE_SIXTEENTH_NOT_HASH_HALF")["passed"],
        "all_zero_not_equivalence_test_pass": next(row for row in semantics["tests"] if row["test"] == "ALL_ZERO_NEVER_UPGRADED_TO_EQUIVALENCE")["passed"],
        "22_family_10pp_power_at_least_80pct": p10 >= .80,
        "22_family_equivalence_power_below_80_disclosed": eq0 < .80 and power["partially_outcome_exposed_no_equivalence_claim"],
        "no_amendment_execution_rows_yet": not (OUT / "EXECUTION_ROWS.json").exists(),
        "no_new_external_model_calls": qualification["external_model_calls_added"] == 0 and measurement["external_model_calls_added"] == 0,
    }
    result = {
        "schema": "paper3.rq2.v4_amendment.preexecution_gate.v1",
        "status": "PASS" if all(checks.values()) else "FAIL_STOP_NO_EXECUTION",
        "checks": checks,
        "power_10pp": p10,
        "equivalence_power_zero": eq0,
        "known_outcome_exposure": "82 slots and 5248 old-C traces were already exposed; amendment is exploratory",
        "external_model_calls_added": 0,
    }
    write_json(OUT / "PREEXECUTION_GATE.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
