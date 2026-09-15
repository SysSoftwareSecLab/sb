"""Hash-bind every scientific input and implementation before the first call."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    target = HERE / "SCIENTIFIC_FREEZE.json"
    if target.exists():
        raise RuntimeError("SCIENTIFIC_FREEZE_ALREADY_EXISTS")
    names = [
        "PROTOCOL.md", "ATOMIC_MODULE_AND_COMPOSER_CONTRACT.md", "ANALYSIS_PLAN.json",
        "FAMILY_BLUEPRINT.json", "FAMILY_CONTRACTS.json", "FAMILY_TOPOLOGIES.json", "FAMILY_TOPOLOGY_AUDIT.json", "MODEL_PROFILES.json",
        "MODEL_PROVENANCE.json", "REFERENCE_TASK_CATALOG.json", "GENERATION_MANIFEST.json",
        "frozen_composer.py", "direct_p_oracle.py", "atomic_isolation.py",
        "atomic_contract_oracle.py", "collect_generation.py", "qualify_and_execute.py",
        "analyze_rq2.py", "HUMAN_REVIEW_PROTOCOL.md", "build_human_package.py",
        "review_app.py", "adjudication_app.py", "power_simulation.py",
        "POWER_SIMULATION_RESULT.json", "PRECALL_POWER_RATIONALE.json",
        "validate_design.py", "DESIGN_VALIDATION_RESULT.json", "validate_precall_gate.py",
        "PRECALL_GATE_RESULT.json", "COLLECTOR_ZERO_CALL_CHECK.json",
        "FULL_REFERENCE_QUALIFICATION.json", "FULL_REFERENCE_QUALIFICATION_ROWS.json",
        "ATOMIC_REFERENCE_QUALIFICATION.json", "ORACLE_BOUNDARY_QUALIFICATION.json",
        "test_frozen_composer.py", "test_atomic_contract_oracle.py", "test_analysis.py",
        "build_generation_manifest.py", "build_reference_study.py", "audit_family_topologies.py", "qualify_full_references.py",
        "qualify_atomic_references.py", "run_oracle_boundary_challenges.py",
        "build_scientific_freeze.py", "SUPERSEDING_CORRECTION.md",
    ]
    paths = [HERE / name for name in names]
    paths.extend(sorted((HERE / "reference_tasks").glob("*/*")))
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError("MISSING_FREEZE_INPUT:" + ",".join(missing))
    unique = sorted(set(paths))
    files = [{"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size} for path in unique]
    precall = json.loads((HERE / "PRECALL_GATE_RESULT.json").read_text(encoding="utf-8"))
    if precall["status"] != "PASS_ALL_CORRECTED_PROTOCOL_GATES" or precall["external_model_calls_for_this_experiment"] != 0:
        raise RuntimeError("PRECALL_GATE_NOT_PASSED")
    freeze = {
        "schema": "paper3.rq2.structure_preserving_recomposition.scientific_freeze.v1",
        "status": "FROZEN_FOR_FINITE_EXECUTION",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "direct_advisor_question": "RQ2: when do task composition, concurrency, and long-range dependency amplify risk?",
        "fixed_generation_slots": 96,
        "fixed_family_clusters": 24,
        "fixed_model_blocks": ["deepseek_flash", "glm5"],
        "fixed_generation_repeats_per_family_model": 2,
        "fixed_factorial_conditions": ["SERIAL_SHORT", "SERIAL_LONG", "CONCURRENT_SHORT", "CONCURRENT_LONG"],
        "fixed_scheduler_seeds": list(range(16)),
        "maximum_factorial_executions": 6144,
        "fixed_confirmatory_contrasts": ["CONCURRENT_MINUS_SERIAL", "LONG_MINUS_SHORT", "CONCURRENCY_BY_DISTANCE_INTERACTION"],
        "negative_outcomes_allowed": ["PRACTICALLY_EQUIVALENT_WITHIN_10PP", "INCONCLUSIVE_OR_HETEROGENEOUS"],
        "resampling_or_result_conditioned_design_changes_forbidden": True,
        "human_transfer": "one two-reviewer package after all machine executions and only if the post-model eligibility gate passes",
        "files": files,
    }
    write_json(target, freeze)
    print(json.dumps({"status": freeze["status"], "files": len(files), "slots": 96}, ensure_ascii=False))


if __name__ == "__main__":
    main()
