"""Validate frozen RQ2 v4 design assets before reference implementation."""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXPECTED_MECHANISMS = {
    "EXCLUSIVE_MOTION_VOLUME_OVERLAP",
    "SUPPORT_OR_BARRIER_VIOLATION",
    "CLEAR_OR_RELEASE_BEFORE_COMMIT",
    "UNSAFE_RECOVERY_INTERFERENCE",
}
REQUIRED_CONTRACT_KEYS = {
    "id",
    "mechanism",
    "a_role",
    "b_role",
    "critical_interval_a",
    "critical_interval_b",
    "safe_predicate",
    "violation_event",
}


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def semantic_hash(row: dict) -> str:
    content = {key: value for key, value in row.items() if key != "id"}
    payload = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    blueprint = load("FAMILY_BLUEPRINT.json")
    contracts = load("FAMILY_CONTRACTS.json")
    analysis = load("ANALYSIS_PLAN.json")
    status = load("STATUS.json")
    power = load("POWER_SIMULATION_RESULT.json")

    blueprint_rows = blueprint["families"]
    contract_rows = contracts["families"]
    blueprint_ids = [row["id"] for row in blueprint_rows]
    contract_ids = [row["id"] for row in contract_rows]
    signatures = {row["id"]: semantic_hash(row) for row in contract_rows}
    topology_audit = load("FAMILY_TOPOLOGY_AUDIT.json")
    mechanism_counts = Counter(row["mechanism"] for row in contract_rows)

    checks = {
        "exactly_24_blueprints": len(blueprint_rows) == 24,
        "exactly_24_contracts": len(contract_rows) == 24,
        "unique_blueprint_ids": len(set(blueprint_ids)) == len(blueprint_ids),
        "unique_contract_ids": len(set(contract_ids)) == len(contract_ids),
        "same_id_set": set(blueprint_ids) == set(contract_ids),
        "all_contract_fields_present": all(REQUIRED_CONTRACT_KEYS <= set(row) for row in contract_rows),
        "four_expected_mechanisms_only": set(mechanism_counts) == EXPECTED_MECHANISMS,
        "six_families_per_mechanism": set(mechanism_counts.values()) == {6},
        "unique_contract_descriptions": len(set(signatures.values())) == 24,
        "implementation_topology_audit_passed": topology_audit["status"] == "PASS"
        and topology_audit["unique_implementation_topologies"] == 24
        and topology_audit["unit_claim"] == "24 fixed scenario families; not 24 independent safety mechanisms",
        "three_confirmatory_contrasts": len(analysis["confirmatory_contrasts"]) == 3,
        "holm_multiplicity_control": analysis["multiplicity"]["method"] == "HOLM",
        "status_counts_match": status["planned_families"] == 24
        and status["planned_atomic_generation_requests"] == 96
        and status["maximum_composed_programs"] == 384,
        "planning_power_at_10pp_at_least_80pct": next(
            row["positive_power_bonferroni_lower_bound"]
            for row in power["scenarios"]
            if row["true_effect"] == 0.1
        ) >= 0.8,
        "equivalence_power_at_zero_at_least_80pct": next(
            row["equivalence_power_bonferroni_tost"]
            for row in power["scenarios"]
            if row["true_effect"] == 0.0
        ) >= 0.8,
    }
    result = {
        "schema": "paper3.rq2.structure_preserving_recomposition.design_validation.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "mechanism_counts": dict(sorted(mechanism_counts.items())),
        "contract_description_hashes": signatures,
        "implementation_topology_hashes": {row["family_id"]: row["implementation_topology_sha256"] for row in topology_audit["rows"]},
        "external_model_calls": 0,
        "meaning": "PASS authorizes reference implementation only; it does not authorize external calls until all protocol pre-call gates pass.",
    }
    write_json(ROOT / "DESIGN_VALIDATION_RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
