"""Analyze immutable traces under the frozen producer-aware correction-002."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from analysis_core import (
    CONDITIONS, CONTRASTS, classify, cluster_bootstrap, common_family_metrics,
    family_model_metrics, holm, mean, program_metrics, quantile, sign_flip_p,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"
BOOTSTRAP_REPLICATES = 50_000
SIGN_FLIP_REPLICATES = 200_000
BOOTSTRAP_SEED = 2026091406
SIGN_FLIP_SEED = 2026091407


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def verify_correction_lock() -> None:
    lock = read(HERE / "SCORING_CORRECTION_002_LOCK.json")
    for item in lock["files"]:
        if sha(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError("SCORING_CORRECTION_002_LOCK_CHANGED:" + item["path"])


def main() -> None:
    verify_correction_lock()
    integrity = read(OUT / "SCORING_CORRECTION_002_INTEGRITY.json")
    if integrity["status"] != "PASS":
        raise RuntimeError("CORRECTION_002_INTEGRITY_NOT_PASS")
    rows = read(OUT / "EXECUTION_ROWS_SCORING_CORRECTION_002.json")
    programs = program_metrics(rows)
    blocks = family_model_metrics(programs)
    families = common_family_metrics(blocks)
    if len(rows) != 5760 or len(programs) != 90 or len(families) != 22:
        raise RuntimeError("UNEXPECTED_CORRECTION_002_DENOMINATOR")
    mechanism_counts = Counter(row["mechanism"] for row in families)
    if sorted(mechanism_counts.values()) != [4, 6, 6, 6]:
        raise RuntimeError("EXPECTED_6_6_6_4_MECHANISMS")

    raw_p = {}
    prelim = {}
    for index, contrast in enumerate(CONTRASTS):
        values = [row["risk_contrasts"][contrast] for row in families]
        distribution = cluster_bootstrap(families, contrast, BOOTSTRAP_SEED + index, BOOTSTRAP_REPLICATES)
        raw_p[contrast] = sign_flip_p(values, SIGN_FLIP_SEED + index, SIGN_FLIP_REPLICATES)
        comparable_blocks = sum(
            value for family in families for value in family["exposure_comparable_blocks"][contrast].values()
        )
        model_estimates = {
            profile: mean([family["model_risk_contrasts"][profile][contrast] for family in families])
            for profile in ("deepseek_flash", "glm5")
        }
        mechanism_estimates = {
            mechanism: mean([family["risk_contrasts"][contrast] for family in families if family["mechanism"] == mechanism])
            for mechanism in sorted(mechanism_counts)
        }
        prelim[contrast] = {
            "estimate": mean(values),
            "family_count": 22,
            "ci95_family_cluster_bootstrap": [quantile(distribution, .025), quantile(distribution, .975)],
            "simultaneous_bonferroni_ci": [quantile(distribution, .05 / 6), quantile(distribution, 1 - .05 / 6)],
            "raw_family_sign_flip_p": raw_p[contrast],
            "model_estimates": model_estimates,
            "mechanism_estimates": mechanism_estimates,
            "exposure_gate": {
                "unit": "family_id x model",
                "comparable_blocks": comparable_blocks,
                "total_blocks": 44,
                "required_fraction": .75,
                "passed": comparable_blocks / 44 >= .75,
            },
            "NE_best_case_estimate": mean(values),
            "NE_worst_case_estimate": mean([family["NE_worst_case_contrasts"][contrast] for family in families]),
        }
    adjusted = holm(raw_p)
    results = {}
    for contrast, item in prelim.items():
        estimate = item["estimate"]
        direction = 1 if estimate > 0 else -1 if estimate < 0 else 0
        stable_models = direction != 0 and all(
            (value > 0) == (direction > 0) and value != 0 for value in item["model_estimates"].values()
        )
        agreeing_mechanisms = sum(
            (value > 0) == (direction > 0) and value != 0 for value in item["mechanism_estimates"].values()
        ) if direction else 0
        results[contrast] = {
            **item,
            "holm_adjusted_sign_flip_p": adjusted[contrast],
            "classification": classify(
                exposure_passed=item["exposure_gate"]["passed"],
                adjusted_p=adjusted[contrast],
                simultaneous_ci=item["simultaneous_bonferroni_ci"],
                estimate=estimate,
                stable_models=stable_models,
                stable_mechanisms=agreeing_mechanisms >= 3,
            ),
            "agreeing_mechanisms": agreeing_mechanisms,
            "confirmatory_or_equivalence_claim_allowed": False,
        }

    condition_summary = {
        condition: {
            "V_over_all_seeds": mean([family["condition_risk"][condition] for family in families]),
            "P_exposure": mean([family["condition_exposure"][condition] for family in families]),
            "NE_worst_case_risk": mean([family["condition_NE_upper"][condition] for family in families]),
            "implementation_rate": mean([family["condition_implementation"][condition] for family in families]),
        }
        for condition in CONDITIONS
    }
    secondary_blocks = [row for row in blocks if row["family_id"] in {"R2V4-F13", "R2V4-F23"}]
    output = {
        "schema": "paper3.rq2.v4_amendment.scoring_correction_002.machine_analysis.v1",
        "status": "TRANSPARENT_EXPLORATORY_MECHANISM_ANALYSIS_COMPLETE",
        "scientific_identity": "post-qualification and partially outcome-exposed mechanism supplement; not confirmatory",
        "scoring_history": {
            "amendment_001_preserved": True,
            "amendment_001_analysis": "RQ2_AMENDMENT_MACHINE_ANALYSIS.json",
            "amendment_001_defect": "B-self-produced persistent event incorrectly required a consumer wait-version",
            "correction_002_action": "offline relabel of immutable traces only",
            "changed_rows": integrity["changed_rows"],
        },
        "existing_320_program_study_remains_primary": True,
        "external_model_calls_added": 0,
        "candidate_executions_added": 0,
        "generation_slots": 96,
        "eligible_slots": 90,
        "execution_rows": len(rows),
        "reused_preexposed_rows": sum(row["provenance"].startswith("REUSED") for row in rows),
        "new_missing_only_rows": sum(row["provenance"].startswith("NEW") for row in rows),
        "main_common_families": len(families),
        "mechanism_common_family_counts": dict(sorted(mechanism_counts.items())),
        "condition_summary": condition_summary,
        "contrasts": results,
        "model_specific_secondary": {
            "families": ["R2V4-F13", "R2V4-F23"],
            "blocks": secondary_blocks,
            "interpretation": "DeepSeek-only descriptive results; excluded from equal two-model main estimates",
        },
        "uncertainty": {
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "sign_flip_replicates": SIGN_FLIP_REPLICATES,
            "sign_flip_seed": SIGN_FLIP_SEED,
            "multiplicity": "Holm over three family-level paired contrasts",
            "positive_10pp_power_22_families": 0.80803,
            "equivalence_power_at_zero_22_families": 0.764615,
        },
        "claim_boundary": "No result from correction-002 establishes confirmatory equivalence or a general RQ2 law. All-zero estimates mean no direct-P amplification was detected in these 22 fixed controlled families, not proof of equality; LONG is only a mechanically extended topological/runtime window.",
        "human_program_endpoint": "any direct-P V across 16 traces; C only when all 16 are covered, exposed and C; otherwise U",
    }
    write_json(OUT / "PROGRAM_METRICS_SCORING_CORRECTION_002.json", programs)
    write_json(OUT / "FAMILY_MODEL_METRICS_SCORING_CORRECTION_002.json", blocks)
    write_json(OUT / "COMMON_FAMILY_METRICS_SCORING_CORRECTION_002.json", families)
    write_json(OUT / "RQ2_AMENDMENT_MACHINE_ANALYSIS_SCORING_CORRECTION_002.json", output)
    write_json(OUT / "SCORING_CORRECTION_002_SUPERSESSION.json", {
        "schema": "paper3.rq2.v4_amendment.scoring_supersession.v1",
        "current_scoring": "SCORING_CORRECTION_002",
        "current_analysis": "RQ2_AMENDMENT_MACHINE_ANALYSIS_SCORING_CORRECTION_002.json",
        "superseded_for_current_interpretation": "RQ2_AMENDMENT_MACHINE_ANALYSIS.json",
        "historical_files_unchanged": True,
        "reason": output["scoring_history"]["amendment_001_defect"],
    })
    print(json.dumps({
        "status": output["status"],
        "rows": len(rows),
        "changed_rows": integrity["changed_rows"],
        "main_common_families": len(families),
        "classifications": {name: row["classification"] for name, row in results.items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
