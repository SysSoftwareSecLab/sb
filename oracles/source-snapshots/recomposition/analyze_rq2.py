"""Frozen family-cluster RQ2 analysis; no model or execution calls."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4"
CONTRASTS = ("CONCURRENT_MINUS_SERIAL", "LONG_MINUS_SHORT", "CONCURRENCY_BY_DISTANCE_INTERACTION")
BOOTSTRAP_SEED = 2026091303
BOOTSTRAP_REPLICATES = 50000
MIN_EXPOSURE_RATE = 0.75
MAX_EXPOSURE_DIFFERENCE = 0.10
MIN_COMPARABLE_FAMILY_FRACTION = 0.75


def read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def verify_freeze() -> None:
    freeze = read(HERE / "SCIENTIFIC_FREEZE.json")
    if freeze["status"] != "FROZEN_FOR_FINITE_EXECUTION":
        raise RuntimeError("SCIENTIFIC_FREEZE_NOT_ACTIVE")
    for item in freeze["files"]:
        if sha(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError("FROZEN_FILE_CHANGED:" + item["path"])


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else math.nan


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def condition_metrics(rows: list[dict]) -> dict:
    by_hash = defaultdict(list)
    for row in rows:
        by_hash[row["schedule_hash"]].append(row)
    hash_states = []
    for schedule_hash_value, group in sorted(by_hash.items()):
        labels = {row["P"] for row in group}
        if len(labels) != 1:
            raise RuntimeError("SAME_SCHEDULE_HASH_HAS_DIFFERENT_P")
        hash_states.append({"schedule_hash": schedule_hash_value, "P": next(iter(labels)), "seed_count": len(group)})
    trace_type_labels = [row["P"] for row in hash_states]
    seed_labels = [row["P"] for row in rows]
    exposed = [label for label in seed_labels if label in {"C", "V"}]
    implemented = [
        bool(row.get("lifecycle_complete"))
        and bool(row.get("cleanup_ok"))
        and row.get("process_status", "EXITED") == "EXITED"
        and row.get("api_error_count", 0) == 0
        for row in rows
    ]
    return {
        "seed_count": len(rows),
        "distinct_interleavings": len(hash_states),
        "duplicate_seed_count": len(rows) - len(hash_states),
        "P_counts_by_protocol_seed": {label: seed_labels.count(label) for label in ("C", "V", "NE")},
        "P_counts_distinct_trace_types": {label: trace_type_labels.count(label) for label in ("C", "V", "NE")},
        "protocol_seed_V_incidence": seed_labels.count("V") / len(seed_labels),
        "P_exposure_rate": len(exposed) / len(seed_labels),
        "V_rate_given_exposure": seed_labels.count("V") / len(exposed) if exposed else None,
        "program_any_V": "V" in seed_labels,
        "program_all_exposed_C": all(label == "C" for label in seed_labels),
        "distinct_trace_type_V_rate": trace_type_labels.count("V") / len(trace_type_labels),
        "treatment_implementation_rate": sum(implemented) / len(implemented),
        "lifecycle_complete_seed_rate": sum(bool(row["lifecycle_complete"]) for row in rows) / len(rows),
        "cleanup_seed_rate": sum(bool(row["cleanup_ok"]) for row in rows) / len(rows),
    }


def factorial_contrasts(values: dict[str, float]) -> dict[str, float]:
    return {
        "CONCURRENT_MINUS_SERIAL": mean([values["CONCURRENT_SHORT"], values["CONCURRENT_LONG"]]) - mean([values["SERIAL_SHORT"], values["SERIAL_LONG"]]),
        "LONG_MINUS_SHORT": mean([values["SERIAL_LONG"], values["CONCURRENT_LONG"]]) - mean([values["SERIAL_SHORT"], values["CONCURRENT_SHORT"]]),
        "CONCURRENCY_BY_DISTANCE_INTERACTION": (values["CONCURRENT_LONG"] - values["CONCURRENT_SHORT"]) - (values["SERIAL_LONG"] - values["SERIAL_SHORT"]),
    }


def exposure_comparable(condition_exposure: dict[str, float], contrast: str) -> bool:
    if contrast == "CONCURRENT_MINUS_SERIAL":
        left = mean([condition_exposure["CONCURRENT_SHORT"], condition_exposure["CONCURRENT_LONG"]])
        right = mean([condition_exposure["SERIAL_SHORT"], condition_exposure["SERIAL_LONG"]])
        return min(left, right) >= MIN_EXPOSURE_RATE and abs(left - right) <= MAX_EXPOSURE_DIFFERENCE
    if contrast == "LONG_MINUS_SHORT":
        left = mean([condition_exposure["SERIAL_LONG"], condition_exposure["CONCURRENT_LONG"]])
        right = mean([condition_exposure["SERIAL_SHORT"], condition_exposure["CONCURRENT_SHORT"]])
        return min(left, right) >= MIN_EXPOSURE_RATE and abs(left - right) <= MAX_EXPOSURE_DIFFERENCE
    values = list(condition_exposure.values())
    return min(values) >= MIN_EXPOSURE_RATE and max(values) - min(values) <= MAX_EXPOSURE_DIFFERENCE


def program_metrics(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["slot_id"], row["condition"])].append(row)
    per_slot = defaultdict(dict)
    metadata = {}
    for (slot_id, condition), group in groups.items():
        per_slot[slot_id][condition] = condition_metrics(group)
        metadata[slot_id] = {key: group[0][key] for key in ("family_id", "mechanism", "profile", "repeat")}
    output = []
    expected = {"SERIAL_SHORT", "SERIAL_LONG", "CONCURRENT_SHORT", "CONCURRENT_LONG"}
    for slot_id, conditions in sorted(per_slot.items()):
        if set(conditions) != expected:
            raise RuntimeError("MISSING_FACTORIAL_CONDITION:" + slot_id)
        risk = {condition: conditions[condition]["protocol_seed_V_incidence"] for condition in expected}
        exposure = {condition: conditions[condition]["P_exposure_rate"] for condition in expected}
        completion = {condition: conditions[condition]["treatment_implementation_rate"] for condition in expected}
        any_v = {condition: float(conditions[condition]["program_any_V"]) for condition in expected}
        contrasts = factorial_contrasts(risk)
        output.append({
            "slot_id": slot_id,
            **metadata[slot_id],
            "conditions": conditions,
            "contrasts": contrasts,
            "exposure_contrasts": factorial_contrasts(exposure),
            "completion_contrasts": factorial_contrasts(completion),
            "program_any_V_contrasts": factorial_contrasts(any_v),
            "condition_exposure": exposure,
            "condition_completion": completion,
            "exposure_comparable": {contrast: exposure_comparable(exposure, contrast) for contrast in CONTRASTS},
            "any_emergent_P": any(value > 0 for value in risk.values()),
        })
    return output


def family_metrics(programs: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in programs:
        groups[row["family_id"]].append(row)
    output = []
    for family_id, rows in sorted(groups.items()):
        by_model = defaultdict(list)
        for row in rows:
            by_model[row["profile"]].append(row)
        model_rows = []
        for profile, repeats in sorted(by_model.items()):
            model_rows.append({
                "profile": profile,
                "repeat_count": len(repeats),
                "contrasts": {contrast: mean([row["contrasts"][contrast] for row in repeats]) for contrast in CONTRASTS},
                "program_any_V_contrasts": {contrast: mean([row["program_any_V_contrasts"][contrast] for row in repeats]) for contrast in CONTRASTS},
                "condition_exposure": {condition: mean([row["condition_exposure"][condition] for row in repeats]) for condition in rows[0]["condition_exposure"]},
                "condition_completion": {condition: mean([row["condition_completion"][condition] for row in repeats]) for condition in rows[0]["condition_completion"]},
                "any_emergent_P_program_rate": mean([float(row["any_emergent_P"]) for row in repeats]),
            })
        family_exposure = {condition: mean([row["condition_exposure"][condition] for row in model_rows]) for condition in rows[0]["condition_exposure"]}
        output.append({
            "family_id": family_id,
            "mechanism": rows[0]["mechanism"],
            "eligible_programs": len(rows),
            "profiles_present": [row["profile"] for row in model_rows],
            "model_rows": model_rows,
            "aggregation_order": "repeat_mean_within_model_then_equal_model_mean_within_family",
            "contrasts": {contrast: mean([row["contrasts"][contrast] for row in model_rows]) for contrast in CONTRASTS},
            "program_any_V_contrasts": {contrast: mean([row["program_any_V_contrasts"][contrast] for row in model_rows]) for contrast in CONTRASTS},
            "condition_exposure": family_exposure,
            "condition_completion": {condition: mean([row["condition_completion"][condition] for row in model_rows]) for condition in rows[0]["condition_completion"]},
            "exposure_comparable": {contrast: exposure_comparable(family_exposure, contrast) for contrast in CONTRASTS},
            "any_emergent_P_program_rate": mean([row["any_emergent_P_program_rate"] for row in model_rows]),
        })
    return output


def bootstrap_distribution(families: list[dict], contrast: str, seed_offset: int = 0) -> list[float]:
    strata = defaultdict(list)
    for row in families:
        strata[row["mechanism"]].append(row["contrasts"][contrast])
    rng = random.Random(BOOTSTRAP_SEED + seed_offset)
    distribution = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = []
        for values in strata.values():
            sampled.extend(rng.choice(values) for _ in values)
        distribution.append(mean(sampled))
    return distribution


def raw_two_sided_p(distribution: list[float]) -> float:
    below = (sum(value <= 0 for value in distribution) + 1) / (len(distribution) + 1)
    above = (sum(value >= 0 for value in distribution) + 1) / (len(distribution) + 1)
    return min(1.0, 2 * min(below, above))


def holm_adjust(raw: dict[str, float]) -> dict[str, float]:
    ordered = sorted(raw, key=raw.get)
    adjusted = {}
    running = 0.0
    total = len(ordered)
    for rank, name in enumerate(ordered):
        running = max(running, (total - rank) * raw[name])
        adjusted[name] = min(1.0, running)
    return adjusted


def subgroup_estimates(programs: list[dict], key: str, contrast: str) -> dict[str, float]:
    grouped = defaultdict(lambda: defaultdict(list))
    for row in programs:
        grouped[row[key]][row["family_id"]].append(row["contrasts"][contrast])
    return {
        group: mean([mean(values) for values in families.values()])
        for group, families in sorted(grouped.items())
    }


def model_estimates(families: list[dict], contrast: str) -> dict[str, float]:
    grouped = defaultdict(list)
    for family in families:
        for row in family["model_rows"]:
            grouped[row["profile"]].append(row["contrasts"][contrast])
    return {profile: mean(values) for profile, values in sorted(grouped.items())}


def main() -> None:
    verify_freeze()
    rows = read(RUN / "EXECUTION_ROWS.json")
    programs = program_metrics(rows)
    families = family_metrics(programs)
    if len(families) != 24:
        raise RuntimeError("POSTMODEL_FAMILY_GATE_NOT_MET")
    profiles = sorted({profile for family in families for profile in family["profiles_present"]})
    common_families = [family for family in families if set(family["profiles_present"]) == set(profiles)]
    if len(profiles) != 2 or len(common_families) != 24:
        raise RuntimeError("POSTMODEL_COMMON_MODEL_FAMILY_GATE_NOT_MET")
    families = common_families
    raw_p = {}
    preliminary = {}
    distributions = {}
    for index, contrast in enumerate(CONTRASTS):
        values = [row["contrasts"][contrast] for row in families]
        distribution = bootstrap_distribution(families, contrast, index * 100000)
        distributions[contrast] = distribution
        raw_p[contrast] = raw_two_sided_p(distribution)
        loo = [mean([other["contrasts"][contrast] for other in families if other["family_id"] != row["family_id"]]) for row in families]
        preliminary[contrast] = {
            "estimate": mean(values),
            "family_count": len(values),
            "ci95": [quantile(distribution, 0.025), quantile(distribution, 0.975)],
            "simultaneous_bonferroni_ci": [quantile(distribution, 0.05 / 6), quantile(distribution, 1 - 0.05 / 6)],
            "equivalence_ci_96_667pct": [quantile(distribution, 0.05 / 3), quantile(distribution, 1 - 0.05 / 3)],
            "raw_bootstrap_p": raw_p[contrast],
            "leave_one_family_out_min": min(loo),
            "leave_one_family_out_max": max(loo),
            "model_estimates": model_estimates(families, contrast),
            "mechanism_estimates": {
                mechanism: mean([row["contrasts"][contrast] for row in families if row["mechanism"] == mechanism])
                for mechanism in sorted({row["mechanism"] for row in families})
            },
            "exposure_gate": {
                "minimum_exposure_rate": MIN_EXPOSURE_RATE,
                "maximum_absolute_exposure_difference": MAX_EXPOSURE_DIFFERENCE,
                "required_comparable_family_fraction": MIN_COMPARABLE_FAMILY_FRACTION,
                "comparable_families": sum(row["exposure_comparable"][contrast] for row in families),
                "family_count": len(families),
            },
        }
    adjusted = holm_adjust(raw_p)
    results = {}
    for contrast in CONTRASTS:
        item = preliminary[contrast]
        estimate = item["estimate"]
        direction = 1 if estimate > 0 else -1 if estimate < 0 else 0
        model_same = all((value > 0) == (direction > 0) and value != 0 for value in item["model_estimates"].values()) if direction else False
        loo_same = item["leave_one_family_out_min"] > 0 if direction > 0 else item["leave_one_family_out_max"] < 0 if direction < 0 else False
        mechanisms_same = sum((value > 0) == (direction > 0) and value != 0 for value in item["mechanism_estimates"].values())
        ci = item["simultaneous_bonferroni_ci"]
        excludes_zero = ci[0] > 0 or ci[1] < 0
        eq_ci = item["equivalence_ci_96_667pct"]
        exposure_gate = item["exposure_gate"]
        exposure_gate["passed"] = (
            exposure_gate["comparable_families"] / exposure_gate["family_count"] >= MIN_COMPARABLE_FAMILY_FRACTION
        )
        equivalent = exposure_gate["passed"] and eq_ci[0] > -0.1 and eq_ci[1] < 0.1
        if not exposure_gate["passed"]:
            statistical = "P_EFFECT_NOT_IDENTIFIABLE_DUE_TO_EXPOSURE_OR_IMPLEMENTATION"
        elif adjusted[contrast] <= 0.05 and excludes_zero:
            statistical = "POSITIVE_EFFECT" if estimate > 0 else "NEGATIVE_EFFECT"
        elif equivalent:
            statistical = "PRACTICALLY_EQUIVALENT_WITHIN_10PP"
        else:
            statistical = "INCONCLUSIVE_OR_HETEROGENEOUS"
        results[contrast] = {
            **item,
            "holm_adjusted_p": adjusted[contrast],
            "statistical_classification": statistical,
            "machine_positive_gate_before_human": bool(
                exposure_gate["passed"] and estimate > 0 and adjusted[contrast] <= 0.05 and ci[0] > 0 and loo_same and model_same and mechanisms_same >= 3
            ),
            "human_program_any_V_corroboration": "PENDING_BLINDED_REVIEW_ON_MATCHED_PROGRAM_LEVEL_ANY_V_ENDPOINT",
        }
    summary = {
        "schema": "paper3.rq2.structure_preserving_recomposition.machine_analysis.v1",
        "status": "MACHINE_ANALYSIS_COMPLETE_HUMAN_GATE_PENDING",
        "primary_endpoint": "direct-P V incidence over the 16 fixed protocol scheduler seeds; NE is a separate multistate outcome and P-effect claims require the frozen exposure-comparability gate",
        "trace_type_endpoint": "normalized causal-order trace types are coverage sensitivity only and receive no probability weight",
        "generation_slots": 96,
        "eligible_programs": len(programs),
        "family_clusters": len(families),
        "execution_seed_rows": len(rows),
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "multiplicity": "Holm p-values plus conservative simultaneous Bonferroni intervals for three contrasts",
        "contrasts": results,
        "overall_emergent_P_program_rate": mean([float(row["any_emergent_P"]) for row in programs]),
        "model_aggregation": "repeat mean within model, then equal model mean within family; only common two-model families enter confirmation",
        "exposure_gate": {"minimum_rate": MIN_EXPOSURE_RATE, "maximum_difference": MAX_EXPOSURE_DIFFERENCE, "minimum_comparable_family_fraction": MIN_COMPARABLE_FAMILY_FRACTION},
        "interpretation_rule": "Positive, equivalent, and inconclusive/heterogeneous are all valid fixed-sample outcomes; no additional slots may be added.",
    }
    write_json(RUN / "PROGRAM_CONDITION_METRICS.json", programs)
    write_json(RUN / "FAMILY_METRICS.json", families)
    write_json(RUN / "RQ2_MACHINE_ANALYSIS.json", summary)
    print(json.dumps({"status": summary["status"], "eligible_programs": len(programs), "families": len(families), "classifications": {key: value["statistical_classification"] for key, value in results.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
