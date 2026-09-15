"""Complete pre-specified RQ2 uncertainty outputs without overwriting analysis."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import analyze_human_returns_v2 as base


P = Path(__file__).resolve().parent
ROOT = P.parents[3]
RUN = ROOT / "05_formal/rq2_rq4_identifiable_confirmation_v1"
RETURN = RUN / "human_return_v2"
ORIGINAL = RETURN / "analysis"
OUTPUT = RETURN / "analysis_addendum_001"
STAGING = RETURN / "analysis_addendum_001.staging"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def channel_gate(results: dict[str, dict]) -> dict:
    directions = {channel: base.sign(value["estimate"]) for channel, value in results.items()}
    same = len(set(directions.values())) == 1 and next(iter(directions.values())) != 0
    return {
        "channel_estimates": {channel: value["estimate"] for channel, value in results.items()},
        "channel_stability": {channel: value["passes_channel_stability_gate"] for channel, value in results.items()},
        "directions": directions,
        "all_three_channels_same_nonzero_direction": same,
        "passes_strong_cross_channel_gate": same and all(value["passes_channel_stability_gate"] for value in results.values()),
    }


def safe_primary(rows: list[dict], factors: list[str], metric: str) -> dict:
    families = sorted({row["family"] for row in rows})
    effects = [base.contrast([row for row in rows if row["family"] == family], factors, metric) for family in families]
    if any(value is None for value in effects):
        return {
            "estimable_for_all_eight_families": False,
            "unestimable_families": [family for family, value in zip(families, effects) if value is None],
            "stable_claim_allowed": False,
        }
    result = base.primary_effect(rows, factors, metric)
    result["estimable_for_all_eight_families"] = True
    return result


def main() -> None:
    assert ORIGINAL.exists() and not OUTPUT.exists() and not STAGING.exists()
    original_lock = json.loads((ORIGINAL / "ANALYSIS_LOCK.json").read_text(encoding="utf-8"))
    assert original_lock["status"] == "FROZEN_COMPLETE"
    package = base.read_json(base.PACKAGE_ROOT / "package/PACKAGE.json")
    private_map = base.read_json(base.PACKAGE_ROOT / "PRIVATE_MAP.json")
    reviews = {channel: base.parse_review(path, reviewer, package) for channel, (path, reviewer) in base.REVIEW_FILES.items()}
    channel_rows = base.build_rows(private_map, reviews)
    result = {
        "status": "COMPLETE_PRE_SPECIFIED_OUTCOME_IMPLEMENTATION_AFTER_AGGREGATE_VISIBILITY",
        "scientific_scope": "Additive uncertainty completion only; not an independent confirmation and no change to P_direct_base primary result.",
        "factorial": {},
        "structural_ood": {},
        "cross_channel": {},
    }
    for channel, rows in channel_rows.items():
        factorial = [row for row in rows if row["block"] == "RQ2_FACTORIAL"]
        ood = [row for row in rows if row["block"] == "STRUCTURAL_OOD"]
        result["factorial"][channel] = {}
        for name, factors in base.CONTRASTS.items():
            result["factorial"][channel][name] = {
                "structure_confirmed_violation_lower": safe_primary(factorial, factors, "structure_V_lower"),
                "structure_worst_case_violation_upper": safe_primary(factorial, factors, "structure_V_upper"),
                "P_path_exposure": safe_primary(factorial, factors, "P_exposure"),
                "P_conditional_confirmed_violation": safe_primary(factorial, factors, "P_conditional_lower"),
                "P_conditional_worst_case_violation": safe_primary(factorial, factors, "P_conditional_upper"),
            }
        result["structural_ood"][channel] = {
            "structure_confirmed_violation_lower": base.ood_primary(ood, "structure_V_lower"),
            "structure_worst_case_violation_upper": base.ood_primary(ood, "structure_V_upper"),
            "P_path_exposure": base.ood_primary(ood, "P_exposure"),
        }
    for name in base.CONTRASTS:
        result["cross_channel"][name] = {}
        for metric in ["structure_confirmed_violation_lower", "structure_worst_case_violation_upper", "P_path_exposure"]:
            values = {channel: result["factorial"][channel][name][metric] for channel in channel_rows}
            result["cross_channel"][name][metric] = channel_gate(values)
    for metric in ["structure_confirmed_violation_lower", "structure_worst_case_violation_upper", "P_path_exposure"]:
        values = {channel: result["structural_ood"][channel][metric] for channel in channel_rows}
        result["cross_channel"].setdefault("structural_OOD_minus_development_shape", {})[metric] = channel_gate(values)

    STAGING.mkdir(parents=True)
    write_json(STAGING / "RQ2_SECONDARY_UNCERTAINTY.json", result)
    inputs = [
        ORIGINAL / "ANALYSIS_LOCK.json",
        P / "ANALYSIS_IMPLEMENTATION_ADDENDUM_001.md",
        P / "analyze_rq2_secondary_addendum_v1.py",
        base.REVIEW_FILES["Reviewer1"][0],
        base.REVIEW_FILES["Reviewer2"][0],
    ]
    lock = {
        "status": "FROZEN_COMPLETE",
        "scope": "PRE_SPECIFIED_RQ2_SECONDARY_UNCERTAINTY_COMPLETION_AFTER_AGGREGATE_VISIBILITY",
        "inputs": [{"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size} for path in inputs],
        "outputs": [{"path": "RQ2_SECONDARY_UNCERTAINTY.json", "sha256": sha(STAGING / "RQ2_SECONDARY_UNCERTAINTY.json"),
                     "bytes": (STAGING / "RQ2_SECONDARY_UNCERTAINTY.json").stat().st_size}],
        "no_overwrite_of_original_analysis": True,
        "not_independent_confirmation": True,
        "no_result_dependent_extension": True,
    }
    write_json(STAGING / "ADDENDUM_LOCK.json", lock)
    os.replace(STAGING, OUTPUT)
    passed = []
    for name, metrics in result["cross_channel"].items():
        for metric, value in metrics.items():
            if value["passes_strong_cross_channel_gate"]:
                passed.append(name + ":" + metric)
    print(json.dumps({"status": "COMPLETE", "strong_cross_channel_secondary": passed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
