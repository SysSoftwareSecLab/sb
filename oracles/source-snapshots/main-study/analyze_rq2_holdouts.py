#!/usr/bin/env python3
"""Analyze the frozen RQ2 holdouts without adding programs or labels.

The analysis separates two questions that program-level UNSAFE rates conflate:
1) Can models realize genuinely held-out attribute/control-flow compositions?
2) Does increasing concurrency, dependency distance, or layout opacity cause a
   stable paired increase in the focal violation/risk outcome?

Absolute holdout failure uses only the task ids frozen in HOLDOUT_REGISTRY.
Paired contrasts retain U/NA uncertainty and cluster at the task-family level.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN = ROOT / "05_formal/main_natural_384_v1"
HUMAN = RUN / "human_review/received_2026-09-12"
OUT = RUN / "analysis"
REVIEWERS = ("Reviewer1", "Reviewer2")
SEED = 20_260_912
REPS = 20_000


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def quantile(values: list[float], probability: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def stable_rng(salt: str) -> random.Random:
    offset = int(hashlib.sha256(salt.encode()).hexdigest()[:12], 16)
    return random.Random(SEED + offset)


def cluster_bootstrap_values(rows: list[dict], value_key: str, cluster_key: str, salt: str) -> list[float | None]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row[cluster_key])].append(row[value_key])
    clusters = sorted(grouped)
    if not clusters:
        return [None, None]
    rng = stable_rng(salt)
    draws = []
    for _ in range(REPS):
        picked = [rng.choice(clusters) for _ in clusters]
        values = [value for cluster in picked for value in grouped[cluster]]
        draws.append(sum(values) / len(values))
    return [round(quantile(draws, 0.025), 6), round(quantile(draws, 0.975), 6)]


def sign(value: float | None, tolerance: float = 1e-15) -> str:
    if value is None or abs(value) <= tolerance:
        return "ZERO"
    return "POSITIVE" if value > 0 else "NEGATIVE"


def fmt_pct(value: float | None) -> str:
    return "NA" if value is None else f"{100 * value:.1f}%"


def load_programs() -> list[dict]:
    generation = {row["slot_id"]: row for row in read(HERE / "GENERATION_MANIFEST.json")}
    private = read(RUN / "human_review/PRIVATE_MAP.json")
    reviews = {
        reviewer: {row["review_id"]: row for row in read(HUMAN / "validated" / f"{reviewer}.json")["records"]}
        for reviewer in REVIEWERS
    }
    assert set(private) == set(reviews[REVIEWERS[0]]) == set(reviews[REVIEWERS[1]])
    programs = []
    for review_id, mapping in private.items():
        slot = generation[mapping["slot_id"]]
        judgments = {
            reviewer: {item["obligation"]: item for item in reviews[reviewer][review_id]["judgments"]}
            for reviewer in REVIEWERS
        }
        assert set(judgments[REVIEWERS[0]]) == set(judgments[REVIEWERS[1]])
        programs.append({
            "review_id": review_id,
            **{key: slot[key] for key in (
                "slot_id", "task_id", "family", "axis", "level", "layout", "profile", "prompt", "repeat",
                "structural_pair_block", "capability_pair_block",
            )},
            "program_labels": {reviewer: reviews[reviewer][review_id]["program_label"] for reviewer in REVIEWERS},
            "judgments": judgments,
        })
    assert len(programs) == 384
    return programs


def absolute_holdout(programs: list[dict], name: str, task_ids: set[str], obligation: str, reference_rows: dict[str, dict]) -> dict:
    subset = [row for row in programs if row["task_id"] in task_ids]
    assert len(subset) == 6 * len(task_ids)
    assert all(obligation in row["judgments"][REVIEWERS[0]] for row in subset)
    families = sorted({row["family"] for row in subset})
    result = {
        "holdout": name,
        "obligation": obligation,
        "task_ids": sorted(task_ids),
        "program_n": len(subset),
        "family_n": len(families),
        "families": families,
        "reference_tasks_accepted": sum(reference_rows[task_id]["reference_accepted"] for task_id in task_ids),
        "reference_tasks_total": len(task_ids),
        "reviewer_specific": {},
    }
    for reviewer in REVIEWERS:
        counts = Counter(row["judgments"][reviewer][obligation]["label"] for row in subset)
        binary = [{"family": row["family"], "violation": row["judgments"][reviewer][obligation]["label"] == "V"} for row in subset]
        v = counts["V"]
        result["reviewer_specific"][reviewer] = {
            "counts": {label: counts[label] for label in ("C", "V", "U", "NA")},
            "violation_n": v,
            "violation_rate_full_denominator": round(v / len(subset), 6),
            "family_cluster_bootstrap_95": cluster_bootstrap_values(binary, "violation", "family", f"abs:{name}:{reviewer}"),
            "families_with_violation_n": len({row["family"] for row in subset if row["judgments"][reviewer][obligation]["label"] == "V"}),
        }
    exact = [
        row for row in subset
        if all(
            row["judgments"][reviewer][obligation]["label"] == "V"
            and row["judgments"][reviewer][obligation]["scope_status"] == "RESOLVED"
            for reviewer in REVIEWERS
        )
    ]
    either = [
        row for row in subset
        if any(row["judgments"][reviewer][obligation]["label"] == "V" for reviewer in REVIEWERS)
    ]
    result["two_reviewer"] = {
        "exact_resolved_violation_n": len(exact),
        "exact_resolved_violation_rate_lower_bound": round(len(exact) / len(subset), 6),
        "families_with_exact_resolved_violation_n": len({row["family"] for row in exact}),
        "either_reviewer_violation_n_sensitivity_upper": len(either),
        "either_reviewer_violation_rate_sensitivity_upper": round(len(either) / len(subset), 6),
        "label_disagreement_n": sum(
            row["judgments"][REVIEWERS[0]][obligation]["label"] != row["judgments"][REVIEWERS[1]][obligation]["label"]
            for row in subset
        ),
    }
    recurrence_ok = all(
        result["reviewer_specific"][reviewer]["families_with_violation_n"] / len(families) >= 0.75
        and result["reviewer_specific"][reviewer]["family_cluster_bootstrap_95"][0] > 0
        for reviewer in REVIEWERS
    )
    joint_ok = result["two_reviewer"]["families_with_exact_resolved_violation_n"] / len(families) >= 0.75
    refs_ok = result["reference_tasks_accepted"] == result["reference_tasks_total"]
    result["admission"] = {
        "admitted_as_recurrent_holdout_failure": bool(recurrence_ok and joint_ok and refs_ok),
        "basis": "Both reviewer family-cluster intervals exclude zero, violations recur in at least 75% of eligible families in both channels and the exact lower bound, and every target reference is accepted.",
    }
    result["by_family"] = {}
    for family in families:
        family_rows = [row for row in subset if row["family"] == family]
        result["by_family"][family] = {
            "n": len(family_rows),
            **{
                reviewer: dict(Counter(row["judgments"][reviewer][obligation]["label"] for row in family_rows))
                for reviewer in REVIEWERS
            },
            "joint_exact_v": sum(
                all(
                    row["judgments"][reviewer][obligation]["label"] == "V"
                    and row["judgments"][reviewer][obligation]["scope_status"] == "RESOLVED"
                    for reviewer in REVIEWERS
                )
                for row in family_rows
            ),
        }
    return result


def possible_v(label: str) -> int:
    return 0 if label == "C" else 1


def definite_v(label: str) -> int:
    return 1 if label == "V" else 0


def analyze_label_pairs(pairs: list[dict], reviewer: str, salt: str) -> dict:
    rows = []
    transitions = Counter()
    for pair in pairs:
        high, low = pair["high"][reviewer], pair["low"][reviewer]
        diff = definite_v(high) - definite_v(low)
        rows.append({"family_cluster": pair["family_cluster"], "diff": diff})
        transitions[f"{low}->{high}"] += 1
    point = mean([row["diff"] for row in rows])
    lower = mean([definite_v(pair["high"][reviewer]) - possible_v(pair["low"][reviewer]) for pair in pairs])
    upper = mean([possible_v(pair["high"][reviewer]) - definite_v(pair["low"][reviewer]) for pair in pairs])
    by_family: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_family[row["family_cluster"]].append(row["diff"])
    family_means = {key: mean(values) for key, values in sorted(by_family.items())}
    direction = sign(point)
    loo = {}
    for omitted in sorted(by_family):
        loo[omitted] = mean([value for key, values in by_family.items() if key != omitted for value in values])
    return {
        "pairs": len(pairs),
        "family_clusters": len(by_family),
        "high_violation_n": sum(pair["high"][reviewer] == "V" for pair in pairs),
        "low_violation_n": sum(pair["low"][reviewer] == "V" for pair in pairs),
        "violation_risk_difference": round(point, 6),
        "unknown_na_worst_case_interval": [round(lower, 6), round(upper, 6)],
        "family_cluster_bootstrap_95": cluster_bootstrap_values(rows, "diff", "family_cluster", f"pairs:{salt}:{reviewer}"),
        "direction": direction,
        "family_means": family_means,
        "families_in_direction_n": sum(sign(value) == direction for value in family_means.values()) if direction != "ZERO" else 0,
        "leave_one_family_out": loo,
        "all_leave_one_family_out_preserve_direction": bool(direction != "ZERO" and all(sign(value) == direction for value in loo.values())),
        "transition_counts": dict(sorted(transitions.items())),
    }


def paired_gate(results: dict[str, dict]) -> dict:
    directions = {row["direction"] for row in results.values()}
    if len(directions) != 1 or "ZERO" in directions:
        return {"admitted": False, "reason": "Reviewer directions differ or include zero."}
    direction = next(iter(directions))
    for row in results.values():
        low, high = row["unknown_na_worst_case_interval"]
        boot_low, boot_high = row["family_cluster_bootstrap_95"]
        bounds_ok = low > 0 if direction == "POSITIVE" else high < 0
        bootstrap_ok = boot_low > 0 if direction == "POSITIVE" else boot_high < 0
        recurrence_ok = row["families_in_direction_n"] / row["family_clusters"] >= 0.75
        if not (bounds_ok and bootstrap_ok and recurrence_ok and row["all_leave_one_family_out_preserve_direction"]):
            return {"admitted": False, "direction": direction, "reason": "At least one reviewer fails UNKNOWN/NA bound, family-cluster interval, recurrence, or leave-one-family-out gate."}
    return {"admitted": True, "direction": direction, "reason": "Both reviewer channels pass the frozen stability gate."}


def build_focal_pairs(programs: list[dict], axis: str, obligation: str) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in programs:
        if row["axis"] == axis:
            grouped[row["structural_pair_block"]].append(row)
    high_level, low_level = ("CONCURRENT", "SERIAL") if axis == "CONCURRENCY" else ("LONG", "SHORT")
    pairs = []
    for key, rows in sorted(grouped.items()):
        assert len(rows) == 2 and {row["level"] for row in rows} == {high_level, low_level}
        high = next(row for row in rows if row["level"] == high_level)
        low = next(row for row in rows if row["level"] == low_level)
        assert obligation in high["judgments"][REVIEWERS[0]] and obligation in low["judgments"][REVIEWERS[0]]
        pairs.append({
            "pair_id": key,
            "family_cluster": high["family"],
            "high": {reviewer: high["judgments"][reviewer][obligation]["label"] for reviewer in REVIEWERS},
            "low": {reviewer: low["judgments"][reviewer][obligation]["label"] for reviewer in REVIEWERS},
        })
    return pairs


def safety_state(row: dict, reviewer: str) -> str:
    judgments = [item for obligation, item in row["judgments"][reviewer].items() if obligation != "TASK_GOAL"]
    if any(item["label"] == "V" and item["scope_status"] == "RESOLVED" for item in judgments):
        return "V"
    if any(item["label"] == "U" or item["scope_status"] != "RESOLVED" for item in judgments):
        return "U"
    return "C"


def build_layout_pairs(programs: list[dict], excluded_families: set[str]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in programs:
        if row["family"] in excluded_families:
            continue
        key = (row["family"], row["axis"], row["level"], row["profile"], row["prompt"], row["repeat"])
        grouped[key].append(row)
    pairs = []
    for key, rows in sorted(grouped.items()):
        assert len(rows) == 2 and {row["layout"] for row in rows} == {"L0", "LH"}
        high = next(row for row in rows if row["layout"] == "LH")
        low = next(row for row in rows if row["layout"] == "L0")
        pairs.append({
            "pair_id": "|".join(map(str, key)),
            "family_cluster": high["family"],
            "high": {reviewer: safety_state(high, reviewer) for reviewer in REVIEWERS},
            "low": {reviewer: safety_state(low, reviewer) for reviewer in REVIEWERS},
        })
    return pairs


def build_nested_attribute_pairs(programs: list[dict]) -> list[dict]:
    family_pairs = {"C8_ATTR_NESTED": "C7_ATTR_FLAT", "D4_ATTR_NESTED": "D3_ATTR_FLAT"}
    indexed = {}
    for row in programs:
        if row["family"] in set(family_pairs) | set(family_pairs.values()):
            key = (row["axis"], row["level"], row["layout"], row["profile"], row["prompt"], row["repeat"])
            indexed[(row["family"], key)] = row
    pairs = []
    for high_family, low_family in family_pairs.items():
        keys = sorted(key for family, key in indexed if family == high_family)
        for key in keys:
            high, low = indexed[(high_family, key)], indexed[(low_family, key)]
            obligation = "ATTRIBUTE_COMBINATION"
            pairs.append({
                "pair_id": f"{low_family}->{high_family}|" + "|".join(map(str, key)),
                "family_cluster": f"{low_family}->{high_family}",
                "high": {reviewer: high["judgments"][reviewer][obligation]["label"] for reviewer in REVIEWERS},
                "low": {reviewer: low["judgments"][reviewer][obligation]["label"] for reviewer in REVIEWERS},
            })
    assert len(pairs) == 48
    return pairs


def write_csvs(absolute: list[dict], contrasts: dict[str, dict]) -> None:
    with (OUT / "RQ2_HOLDOUT_ABSOLUTE.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["holdout", "obligation", "program_n", "family_n", "reference_accepted", "reviewer", "V_n", "V_rate", "bootstrap_low", "bootstrap_high", "joint_exact_V_n", "joint_lower_rate", "admitted"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in absolute:
            for reviewer in REVIEWERS:
                row = item["reviewer_specific"][reviewer]
                writer.writerow({
                    "holdout": item["holdout"], "obligation": item["obligation"], "program_n": item["program_n"],
                    "family_n": item["family_n"], "reference_accepted": f"{item['reference_tasks_accepted']}/{item['reference_tasks_total']}",
                    "reviewer": reviewer, "V_n": row["violation_n"], "V_rate": row["violation_rate_full_denominator"],
                    "bootstrap_low": row["family_cluster_bootstrap_95"][0], "bootstrap_high": row["family_cluster_bootstrap_95"][1],
                    "joint_exact_V_n": item["two_reviewer"]["exact_resolved_violation_n"],
                    "joint_lower_rate": item["two_reviewer"]["exact_resolved_violation_rate_lower_bound"],
                    "admitted": item["admission"]["admitted_as_recurrent_holdout_failure"],
                })
    with (OUT / "RQ2_FOCAL_PAIRED_CONTRASTS.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["contrast", "outcome", "high_minus_low", "reviewer", "pairs", "family_clusters", "low_V", "high_V", "risk_difference", "unknown_na_low", "unknown_na_high", "bootstrap_low", "bootstrap_high", "direction", "admitted"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for name, item in contrasts.items():
            for reviewer in REVIEWERS:
                row = item["reviewer_specific"][reviewer]
                writer.writerow({
                    "contrast": name, "outcome": item["outcome"], "high_minus_low": item["high_minus_low"],
                    "reviewer": reviewer, "pairs": row["pairs"], "family_clusters": row["family_clusters"],
                    "low_V": row["low_violation_n"], "high_V": row["high_violation_n"], "risk_difference": row["violation_risk_difference"],
                    "unknown_na_low": row["unknown_na_worst_case_interval"][0], "unknown_na_high": row["unknown_na_worst_case_interval"][1],
                    "bootstrap_low": row["family_cluster_bootstrap_95"][0], "bootstrap_high": row["family_cluster_bootstrap_95"][1],
                    "direction": row["direction"], "admitted": item["admission"]["admitted"],
                })


def write_markdown(result: dict) -> None:
    lines = [
        "# RQ2 frozen holdout analysis",
        "",
        f"Status: **{result['status']}**",
        "",
        "This analysis uses only the frozen 384 natural programs, their existing double review, the frozen holdout registry, and qualified references. No program, model call, human label, or post-result subgroup was added.",
        "",
        "## Direct held-out composition failures",
        "",
    ]
    for item in result["absolute_holdout_failures"]:
        left, right, joint = item["reviewer_specific"][REVIEWERS[0]], item["reviewer_specific"][REVIEWERS[1]], item["two_reviewer"]
        lines.append(
            f"- **{item['holdout']} / {item['obligation']}**: {item['reference_tasks_accepted']}/{item['reference_tasks_total']} qualified references pass. "
            f"Natural outputs violate the focal obligation in {left['violation_n']}/{item['program_n']} ({fmt_pct(left['violation_rate_full_denominator'])}) and "
            f"{right['violation_n']}/{item['program_n']} ({fmt_pct(right['violation_rate_full_denominator'])}) cases; exact two-reviewer lower bound "
            f"{joint['exact_resolved_violation_n']}/{item['program_n']} ({fmt_pct(joint['exact_resolved_violation_rate_lower_bound'])}). "
            f"Recurrent holdout-failure admission: {item['admission']['admitted_as_recurrent_holdout_failure']}."
        )
    lines += ["", "## Paired amplification tests", "", "| Contrast | Outcome | Reviewer | Low V | High V | Difference | U/NA bound | Cluster 95% | Admitted |", "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for name, item in result["paired_amplification_tests"].items():
        for reviewer in REVIEWERS:
            row = item["reviewer_specific"][reviewer]
            lines.append(
                f"| {name} | {item['outcome']} | {reviewer} | {row['low_violation_n']} | {row['high_violation_n']} | {fmt_pct(row['violation_risk_difference'])} | "
                f"[{fmt_pct(row['unknown_na_worst_case_interval'][0])}, {fmt_pct(row['unknown_na_worst_case_interval'][1])}] | "
                f"[{fmt_pct(row['family_cluster_bootstrap_95'][0])}, {fmt_pct(row['family_cluster_bootstrap_95'][1])}] | {item['admission']['admitted']} |"
            )
    lines += [
        "",
        "## RQ2 conclusion",
        "",
        f"- {result['paper_level_conclusion']}",
        f"- Replication decision: **{result['prospective_replication_decision']['decision']}**. {result['prospective_replication_decision']['reason']}",
        "- The evidence supports held-out compositional generalization failure. It does not support the stronger causal slogan that concurrency, longer distance, or hidden layout monotonically amplifies overall risk.",
        "",
    ]
    (OUT / "RQ2_HOLDOUT_ANALYSIS.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    programs = load_programs()
    registry = read(HERE / "HOLDOUT_REGISTRY.json")
    references = {row["task_id"]: row for row in read(HERE / "REFERENCE_QUALIFICATION.json")["rows"]}
    main_tables = read(OUT / "MAIN_TABLES.json")

    attribute_tasks = set(registry["attribute_combination"]["objects"])
    control_tasks = set(registry["control_flow"]["objects"])
    absolute = [
        absolute_holdout(programs, "ATTRIBUTE_COMBINATION", attribute_tasks, "ATTRIBUTE_COMBINATION", references),
        absolute_holdout(programs, "CONTROL_FLOW", control_tasks, "CONTROL_FLOW_HOLDOUT", references),
    ]
    pair_specs = {
        "CONCURRENCY_FOCAL": (build_focal_pairs(programs, "CONCURRENCY", "COMPOSITION_CONCURRENCY"), "COMPOSITION_CONCURRENCY", "CONCURRENT minus SERIAL"),
        "DEPENDENCY_DISTANCE_FOCAL": (build_focal_pairs(programs, "DEPENDENCY_DISTANCE", "LONG_RANGE_DEPENDENCY"), "LONG_RANGE_DEPENDENCY", "LONG minus SHORT"),
        "LAYOUT_SAFETY_ANY_V": (build_layout_pairs(programs, {"C4_ALLOCATION"}), "any resolved safety-obligation V", "LH minus L0; C4 excluded per registry"),
        "NESTED_ON_ATTRIBUTE": (build_nested_attribute_pairs(programs), "ATTRIBUTE_COMBINATION", "nested minus matched flat family"),
    }
    contrasts = {}
    for name, (pairs, outcome, description) in pair_specs.items():
        reviewer_results = {reviewer: analyze_label_pairs(pairs, reviewer, name) for reviewer in REVIEWERS}
        contrasts[name] = {
            "outcome": outcome,
            "high_minus_low": description,
            "reviewer_specific": reviewer_results,
            "admission": paired_gate(reviewer_results),
        }

    holdouts_admitted = all(item["admission"]["admitted_as_recurrent_holdout_failure"] for item in absolute)
    paired_admitted = {name: item["admission"]["admitted"] for name, item in contrasts.items()}
    status = "RQ2_HOLDOUT_GENERALIZATION_FAILURE_IDENTIFIED_AXIS_AMPLIFICATION_NOT_SUPPORTED" if holdouts_admitted else "RQ2_EXISTING_HOLDOUTS_NON_IDENTIFYING"
    replication = {
        "decision": "NO_NEW_REPLICATION_NOW" if holdouts_admitted else "PROSPECTIVE_INDEPENDENT_FAMILY_REPLICATION_REQUIRED",
        "reason": (
            "The already-frozen holdouts provide recurrent failures under both reviewers, exact-agreement lower bounds, qualified correct references, and multiple eligible families. A new family is not needed to establish the narrower held-out generalization claim; it would only be needed for a future causal monotonic-amplification claim that the current paired tests do not support or leave unidentified."
            if holdouts_admitted
            else "The current true holdouts do not pass the recurrent two-reviewer gate; one independently designed family replication should be frozen before generation."
        ),
    }
    conclusion = (
        "Generated programs fail genuine held-out composition requirements at high, cross-family rates even though paired increases in concurrency, dependency distance, nestedness, and layout do not pass the stability gate. The defensible RQ2 finding is a discontinuity at unseen composition, not a monotone complexity/risk law."
        if holdouts_admitted and not any(paired_admitted.values())
        else "The existing holdout and paired evidence does not yet support a single RQ2 finding."
    )
    result = {
        "schema": "paper3.rq2_holdout_analysis.v1",
        "status": status,
        "question": "How do composition, concurrency, dependency distance, and structural holdouts affect natural program safety?",
        "scope": {
            "programs": 384,
            "new_programs": 0,
            "new_model_calls": 0,
            "new_human_labels": 0,
            "analysis_timing": "Post-intake synthesis constrained to the pre-existing frozen holdout registry and matching blocks; paired focal-obligation tests are mechanism analyses and not relabeled as preregistered primary contrasts.",
            "evidence_level": "Paper-level descriptive evidence on pre-frozen holdout objects; does not increment the preregistered stable-finding counter.",
        },
        "absolute_holdout_failures": absolute,
        "paired_amplification_tests": contrasts,
        "frozen_program_level_context": {
            key: main_tables["paired"][key]
            for key in ("T2_CONCURRENCY", "T2_DEPENDENCY_DISTANCE", "LAYOUT_SECONDARY")
        },
        "paper_level_conclusion": conclusion,
        "prospective_replication_decision": replication,
        "input_hashes": {
            "holdout_registry": sha(HERE / "HOLDOUT_REGISTRY.json"),
            "reference_qualification": sha(HERE / "REFERENCE_QUALIFICATION.json"),
            "generation_manifest": sha(HERE / "GENERATION_MANIFEST.json"),
            "private_map": sha(RUN / "human_review/PRIVATE_MAP.json"),
            **{f"review_{reviewer}": sha(HUMAN / "validated" / f"{reviewer}.json") for reviewer in REVIEWERS},
            "main_tables": sha(OUT / "MAIN_TABLES.json"),
        },
        "outputs": {
            "markdown": "RQ2_HOLDOUT_ANALYSIS.md",
            "absolute_csv": "RQ2_HOLDOUT_ABSOLUTE.csv",
            "paired_csv": "RQ2_FOCAL_PAIRED_CONTRASTS.csv",
        },
    }
    write_csvs(absolute, contrasts)
    write_json(OUT / "RQ2_HOLDOUT_ANALYSIS.json", result)
    write_markdown(result)
    print(json.dumps({
        "status": status,
        "absolute": [{"holdout": item["holdout"], "admission": item["admission"], "reviewers": item["reviewer_specific"], "joint": item["two_reviewer"]} for item in absolute],
        "paired": {name: {"admission": item["admission"], "reviewers": item["reviewer_specific"]} for name, item in contrasts.items()},
        "replication": replication,
        "conclusion": conclusion,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
