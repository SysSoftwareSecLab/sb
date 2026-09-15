"""Single zero-call audit of every pre-call gate in PROTOCOL.md section 7."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4"


def read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def provenance_count(relative_root: str, model: str) -> tuple[int, int]:
    matching = identity = 0
    for path in (ROOT / relative_root).rglob("RESULT.json"):
        try:
            value = read(path)
        except (ValueError, OSError):
            continue
        if value.get("response_model") == model:
            matching += 1
            identity += int(value.get("model_identity_matches") is True)
    return matching, identity


def main() -> None:
    checks = {}
    full = read(HERE / "FULL_REFERENCE_QUALIFICATION.json")
    checks["reference_24_families_1536_executions"] = full["status"] == "PASS" and full["families"] == 24 and full["accepted_executions"] == 1536
    checks["reference_action_and_schedule_gates"] = all(
        row["static_composer_audit_passed"]
        and row["one_action_multiset_per_condition"]
        and row["action_multiset_equal_across_four_conditions"]
        and row["concurrent_distinct_schedule_hashes"] >= 2
        for row in full["family_summaries"]
    )
    atomic = read(HERE / "ATOMIC_REFERENCE_QUALIFICATION.json")
    checks["atomic_reference_48_of_48"] = (
        atomic["status"] == "PASS" and atomic["accepted_atomic_executions"] == 48
        and all(row.get("static_contract_ok") and row.get("dynamic_contract_ok") for row in atomic["rows"])
    )
    boundary = read(HERE / "ORACLE_BOUNDARY_QUALIFICATION.json")
    checks["oracle_boundary_36_of_36"] = boundary["status"] == "PASS" and boundary.get("oracle_classes") == 9 and len(boundary["rows"]) == 36 and all(row["passed"] for row in boundary["rows"])
    design = read(HERE / "DESIGN_VALIDATION_RESULT.json")
    topology = read(HERE / "FAMILY_TOPOLOGY_AUDIT.json")
    checks["family_implementation_topologies_and_analysis_design"] = design["status"] == "PASS" and topology["status"] == "PASS" and topology["unique_implementation_topologies"] == 24
    analysis = read(HERE / "ANALYSIS_PLAN.json")
    checks["exposure_seed_model_and_human_rules_frozen"] = (
        analysis["primary_endpoint"] == "DIRECT_P_V_INCIDENCE_OVER_16_FIXED_PROTOCOL_SCHEDULER_SEEDS_WITH_EXPOSURE_GATE"
        and analysis["exposure_identifiability_gate"]["minimum_exposure_rate_per_compared_arm"] == 0.75
        and analysis["exposure_identifiability_gate"]["maximum_absolute_exposure_rate_difference"] == 0.1
        and analysis["model_missingness"]["minimum_common_model_families"] == 24
        and "程序级any-V" in (HERE / "HUMAN_REVIEW_PROTOCOL.md").read_text(encoding="utf-8")
    )
    power = read(HERE / "POWER_SIMULATION_RESULT.json")
    by_effect = {row["true_effect"]: row for row in power["scenarios"]}
    checks["power_and_equivalence_above_80pct"] = by_effect[0.1]["positive_power_bonferroni_lower_bound"] >= 0.8 and by_effect[0.0]["equivalence_power_bonferroni_tost"] >= 0.8
    manifest = read(HERE / "GENERATION_MANIFEST.json")
    checks["manifest_96_unique_fixed_slots"] = len(manifest) == 96 and len({row["slot_id"] for row in manifest}) == 96
    checks["manifest_balance"] = Counter(row["profile"] for row in manifest) == {"deepseek_flash": 48, "glm5": 48} and all(sum(row["family_id"] == family for row in manifest) == 4 for family in {row["family_id"] for row in manifest})
    checks["manifest_hash_bindings_current"] = all(
        row["prompt_sha256"] == sha(HERE / row["prompt_path"])
        and row["spec_sha256"] == sha(HERE / row["spec_path"])
        for row in manifest
    )
    factors = re.compile(r"SERIAL|CONCURRENT|SHORT|LONG|串行|并发|长依赖|短依赖", re.IGNORECASE)
    checks["generator_factor_blinding"] = not any(factors.search(row["request"]["messages"][1]["content"]) for row in manifest)
    qualified_prompt_hashes = {row["family_id"]: row["prompt_sha256"] for row in full["family_summaries"]}
    checks["qualified_prompts_are_manifest_prompts"] = all(qualified_prompt_hashes[row["family_id"]] == row["prompt_sha256"] for row in manifest)
    collector = read(HERE / "COLLECTOR_ZERO_CALL_CHECK.json")
    checks["collector_and_credentials_zero_call_gate"] = collector["status"] == "PASS" and collector["scientific_calls"] == 0 and collector["candidate_execution_in_collector"] is False
    provenance = read(HERE / "MODEL_PROVENANCE.json")
    provenance_checks = []
    for row in provenance["profiles"]:
        matching, identity = provenance_count(row["evidence_root"], row["expected_response_model"])
        provenance_checks.append(matching == row["matching_result_receipts"] and identity == row["identity_match_receipts"])
    checks["model_identity_provenance_matches_raw_receipts"] = all(provenance_checks)
    checks["postmodel_and_analysis_code_present"] = all((HERE / name).exists() for name in (
        "atomic_contract_oracle.py", "qualify_and_execute.py", "analyze_rq2.py",
        "HUMAN_REVIEW_PROTOCOL.md", "build_human_package.py", "review_app.py", "adjudication_app.py",
    ))
    checks["workload_within_authorized_capacity"] = 384 * 15 / 60 * 1.25 <= 150
    prior_results = list((RUN / "generation").rglob("RESULT.json")) if (RUN / "generation").exists() else []
    checks["no_rq2_v4_model_results_visible_before_freeze"] = not prior_results
    result = {
        "schema": "paper3.rq2.structure_preserving_recomposition.precall_gate.v1",
        "status": "PASS_ALL_CORRECTED_PROTOCOL_GATES" if all(checks.values()) else "FAIL_NO_EXTERNAL_CALLS",
        "checks": checks,
        "external_model_calls_for_this_experiment": 0,
        "human_review_packages": 0,
        "planned_generation_calls": 96,
        "maximum_factorial_executions": 6144,
        "maximum_human_objects_per_reviewer": 384,
    }
    write_json(HERE / "PRECALL_GATE_RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS_ALL_CORRECTED_PROTOCOL_GATES":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
