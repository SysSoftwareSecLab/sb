"""Frozen-unit RQ2 amendment aggregation and inference helpers."""
from __future__ import annotations

from collections import defaultdict
import math
import random
import statistics


CONTRASTS = (
    "CONCURRENT_MINUS_SERIAL",
    "LONG_MINUS_SHORT",
    "CONCURRENCY_BY_DISTANCE_INTERACTION",
)
CONDITIONS = ("SERIAL_SHORT", "SERIAL_LONG", "CONCURRENT_SHORT", "CONCURRENT_LONG")
MIN_EXPOSURE = 0.75
MAX_EXPOSURE_DIFF = 0.10


def mean(values):
    return statistics.fmean(values) if values else math.nan


def quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def factorial_contrasts(values):
    return {
        "CONCURRENT_MINUS_SERIAL": mean([values["CONCURRENT_SHORT"], values["CONCURRENT_LONG"]]) - mean([values["SERIAL_SHORT"], values["SERIAL_LONG"]]),
        "LONG_MINUS_SHORT": mean([values["SERIAL_LONG"], values["CONCURRENT_LONG"]]) - mean([values["SERIAL_SHORT"], values["CONCURRENT_SHORT"]]),
        "CONCURRENCY_BY_DISTANCE_INTERACTION": (values["CONCURRENT_LONG"] - values["CONCURRENT_SHORT"]) - (values["SERIAL_LONG"] - values["SERIAL_SHORT"]),
    }


def condition_metrics(rows):
    labels = [row["P_new"] for row in rows]
    if len(rows) != 16 or any(label not in {"C", "V", "NE"} for label in labels):
        raise RuntimeError("CONDITION_MUST_HAVE_16_C_V_NE_ROWS")
    exposed = labels.count("C") + labels.count("V")
    implemented = [
        bool(row.get("lifecycle_complete")) and row.get("process_status") == "EXITED"
        and row.get("returncode") == 0 and row.get("api_error_count", 0) == 0
        and bool(row.get("cleanup_ok"))
        for row in rows
    ]
    return {
        "seed_count": len(rows),
        "P_counts": {label: labels.count(label) for label in ("C", "V", "NE")},
        "V_over_all_seeds": labels.count("V") / len(labels),
        "P_exposure": exposed / len(labels),
        "V_given_exposure": labels.count("V") / exposed if exposed else None,
        "NE_best_case_risk": labels.count("V") / len(labels),
        "NE_worst_case_risk": (labels.count("V") + labels.count("NE")) / len(labels),
        "implementation_rate": sum(implemented) / len(implemented),
        "program_any_V": "V" in labels,
        "program_all_exposed_C": all(label == "C" for label in labels),
        "distinct_schedule_hashes": len({row["schedule_hash_new"] for row in rows}),
    }


def program_metrics(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["slot_id"], row["condition"])].append(row)
    per_slot = defaultdict(dict)
    metadata = {}
    for (slot_id, condition), group in groups.items():
        per_slot[slot_id][condition] = condition_metrics(group)
        metadata[slot_id] = {key: group[0][key] for key in ("family_id", "mechanism", "profile", "repeat")}
    output = []
    for slot_id, conditions in sorted(per_slot.items()):
        if set(conditions) != set(CONDITIONS):
            raise RuntimeError("MISSING_FACTORIAL_CONDITION:" + slot_id)
        risk = {condition: conditions[condition]["V_over_all_seeds"] for condition in CONDITIONS}
        exposure = {condition: conditions[condition]["P_exposure"] for condition in CONDITIONS}
        ne_upper = {condition: conditions[condition]["NE_worst_case_risk"] for condition in CONDITIONS}
        output.append({
            "slot_id": slot_id,
            **metadata[slot_id],
            "conditions": conditions,
            "risk_contrasts": factorial_contrasts(risk),
            "exposure_contrasts": factorial_contrasts(exposure),
            "NE_worst_case_contrasts": factorial_contrasts(ne_upper),
        })
    return output


def equal_repeat_then_model(values_by_model):
    return mean([mean(repeats) for repeats in values_by_model.values()])


def exposure_comparable(condition_exposure, contrast):
    if contrast == "CONCURRENT_MINUS_SERIAL":
        treated = mean([condition_exposure["CONCURRENT_SHORT"], condition_exposure["CONCURRENT_LONG"]])
        control = mean([condition_exposure["SERIAL_SHORT"], condition_exposure["SERIAL_LONG"]])
        return min(treated, control) >= MIN_EXPOSURE and abs(treated - control) <= MAX_EXPOSURE_DIFF
    if contrast == "LONG_MINUS_SHORT":
        treated = mean([condition_exposure["SERIAL_LONG"], condition_exposure["CONCURRENT_LONG"]])
        control = mean([condition_exposure["SERIAL_SHORT"], condition_exposure["CONCURRENT_SHORT"]])
        return min(treated, control) >= MIN_EXPOSURE and abs(treated - control) <= MAX_EXPOSURE_DIFF
    values = list(condition_exposure.values())
    return min(values) >= MIN_EXPOSURE and max(values) - min(values) <= MAX_EXPOSURE_DIFF


def family_model_metrics(programs):
    groups = defaultdict(list)
    for row in programs:
        groups[(row["family_id"], row["profile"])].append(row)
    output = []
    for (family_id, profile), repeats in sorted(groups.items()):
        condition_exposure = {
            condition: mean([row["conditions"][condition]["P_exposure"] for row in repeats])
            for condition in CONDITIONS
        }
        output.append({
            "family_id": family_id,
            "mechanism": repeats[0]["mechanism"],
            "profile": profile,
            "repeat_count": len(repeats),
            "risk_contrasts": {contrast: mean([row["risk_contrasts"][contrast] for row in repeats]) for contrast in CONTRASTS},
            "NE_worst_case_contrasts": {contrast: mean([row["NE_worst_case_contrasts"][contrast] for row in repeats]) for contrast in CONTRASTS},
            "condition_exposure": condition_exposure,
            "exposure_comparable": {contrast: exposure_comparable(condition_exposure, contrast) for contrast in CONTRASTS},
            "condition_risk": {condition: mean([row["conditions"][condition]["V_over_all_seeds"] for row in repeats]) for condition in CONDITIONS},
            "condition_NE_upper": {condition: mean([row["conditions"][condition]["NE_worst_case_risk"] for row in repeats]) for condition in CONDITIONS},
            "condition_implementation": {condition: mean([row["conditions"][condition]["implementation_rate"] for row in repeats]) for condition in CONDITIONS},
            "program_any_V_rate": mean([float(any(row["conditions"][condition]["program_any_V"] for condition in CONDITIONS)) for row in repeats]),
        })
    return output


def common_family_metrics(blocks, profiles=("deepseek_flash", "glm5")):
    groups = defaultdict(list)
    for row in blocks:
        groups[row["family_id"]].append(row)
    output = []
    for family_id, rows in sorted(groups.items()):
        by_profile = {row["profile"]: row for row in rows}
        if set(by_profile) != set(profiles):
            continue
        output.append({
            "family_id": family_id,
            "mechanism": rows[0]["mechanism"],
            "profiles": sorted(by_profile),
            "risk_contrasts": {contrast: mean([by_profile[p]["risk_contrasts"][contrast] for p in profiles]) for contrast in CONTRASTS},
            "NE_worst_case_contrasts": {contrast: mean([by_profile[p]["NE_worst_case_contrasts"][contrast] for p in profiles]) for contrast in CONTRASTS},
            "model_risk_contrasts": {p: by_profile[p]["risk_contrasts"] for p in profiles},
            "exposure_comparable_blocks": {contrast: {p: by_profile[p]["exposure_comparable"][contrast] for p in profiles} for contrast in CONTRASTS},
            "condition_risk": {condition: mean([by_profile[p]["condition_risk"][condition] for p in profiles]) for condition in CONDITIONS},
            "condition_exposure": {condition: mean([by_profile[p]["condition_exposure"][condition] for p in profiles]) for condition in CONDITIONS},
            "condition_NE_upper": {condition: mean([by_profile[p]["condition_NE_upper"][condition] for p in profiles]) for condition in CONDITIONS},
            "condition_implementation": {condition: mean([by_profile[p]["condition_implementation"][condition] for p in profiles]) for condition in CONDITIONS},
        })
    return output


def cluster_bootstrap(families, contrast, seed, replicates=50_000):
    strata = defaultdict(list)
    for row in families:
        strata[row["mechanism"]].append(row["risk_contrasts"][contrast])
    rng = random.Random(seed)
    return [mean([rng.choice(values) for values in strata.values() for _ in values]) for _ in range(replicates)]


def sign_flip_p(values, seed, replicates=200_000):
    observed = abs(mean(values))
    if all(value == 0 for value in values):
        return 1.0
    rng = random.Random(seed)
    extreme = 0
    for _ in range(replicates):
        statistic = abs(mean([value if rng.getrandbits(1) else -value for value in values]))
        extreme += statistic >= observed - 1e-15
    return (extreme + 1) / (replicates + 1)


def holm(raw):
    ordered = sorted(raw, key=raw.get)
    adjusted = {}
    running = 0.0
    for rank, name in enumerate(ordered):
        running = max(running, (len(ordered) - rank) * raw[name])
        adjusted[name] = min(1.0, running)
    return adjusted


def classify(*, exposure_passed, adjusted_p, simultaneous_ci, estimate, stable_models, stable_mechanisms):
    if not exposure_passed:
        return "EXPOSURE_OR_IMPLEMENTATION_NON_IDENTIFIABLE"
    directional = adjusted_p <= 0.05 and (simultaneous_ci[0] > 0 or simultaneous_ci[1] < 0)
    if directional and stable_models and stable_mechanisms:
        return "EXPLORATORY_STABLE_MECHANISM_SIGNAL"
    if estimate == 0 and simultaneous_ci == [0.0, 0.0]:
        return "NO_DETECTABLE_DIRECT_P_AMPLIFICATION_IN_22_FIXED_FAMILIES__EQUIVALENCE_NOT_ESTABLISHED"
    return "EXPLORATORY_INCONCLUSIVE_OR_MECHANISM_HETEROGENEOUS"
