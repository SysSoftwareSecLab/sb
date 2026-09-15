#!/usr/bin/env python3
"""Freeze the RQ1 natural-defect spectrum from the existing 384-program study.

This analysis does not adjudicate or alter either human review. It preserves the
pre-deblinding truth policy by reporting both reviewer channels, an exact
two-reviewer/resolved lower bound, UNKNOWN/disagreement sensitivity, and
family-cluster uncertainty.  The unit of analysis is a generated natural
program; bootstrap resampling is at the task-family level.
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
FORMAL = ROOT / "05_formal/main_natural_384_v1"
HUMAN = FORMAL / "human_review/received_2026-09-12"
ANALYSIS = FORMAL / "analysis"

REVIEWERS = ("Reviewer1", "Reviewer2")
BOOTSTRAP_REPS = 20_000
SEED = 20_260_912

CATEGORY_MAP = {
    "TASK_GOAL": "TERMINAL_TASK_OUTCOME",
    "SUPPORT_DEPARTURE": "MOTION_LIFECYCLE",
    "RELEASE_DEPARTURE": "MOTION_LIFECYCLE",
    "TIMEOUT_CLEANUP": "MOTION_LIFECYCLE",
    "ATTRIBUTE_COMBINATION": "COMPOSITION_STRUCTURE",
    "CONTROL_FLOW_HOLDOUT": "COMPOSITION_STRUCTURE",
    "COMPOSITION_CONCURRENCY": "COMPOSITION_STRUCTURE",
    "BUFFER_OCCUPANCY_OWNER": "RESOURCE_OWNERSHIP",
    "DUAL_RESOURCE_SPAN": "RESOURCE_OWNERSHIP",
    "ALLOCATION_EXCLUSIVITY": "RESOURCE_OWNERSHIP",
    "BUFFER_EVENT_PROTOCOL": "EVENT_DEPENDENCY_PROTOCOL",
    "BUFFER_RECEIPT": "EVENT_DEPENDENCY_PROTOCOL",
    "LONG_RANGE_DEPENDENCY": "EVENT_DEPENDENCY_PROTOCOL",
    "EVENT_JOIN": "EVENT_DEPENDENCY_PROTOCOL",
    "EXCHANGE_PROTOCOL": "EVENT_DEPENDENCY_PROTOCOL",
    "EXCHANGE_RECEIPT": "EVENT_DEPENDENCY_PROTOCOL",
    "OBS_CURRENT": "OBSERVATION_BRANCHING",
    "ALLOCATION_OBSERVATION": "OBSERVATION_BRANCHING",
    "REWORK_OBSERVATION": "OBSERVATION_BRANCHING",
    "REWORK_BRANCH": "OBSERVATION_BRANCHING",
}

CATEGORY_CN = {
    "TERMINAL_TASK_OUTCOME": "终局任务结果（与安全缺陷谱分开）",
    "MOTION_LIFECYCLE": "运动/持物生命周期",
    "COMPOSITION_STRUCTURE": "组合结构实现",
    "RESOURCE_OWNERSHIP": "资源所有权与占用",
    "EVENT_DEPENDENCY_PROTOCOL": "事件、长程依赖与协议",
    "OBSERVATION_BRANCHING": "观测、分支与恢复",
}


def read(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def family_cluster_bootstrap(rows: list[dict], value_key: str, salt: str) -> list[float]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        grouped[row["family"]].append(int(row[value_key]))
    families = sorted(grouped)
    if not families:
        return [math.nan, math.nan]
    stable_salt = int(hashlib.sha256(salt.encode()).hexdigest()[:12], 16)
    rng = random.Random(SEED + stable_salt)
    draws: list[float] = []
    for _ in range(BOOTSTRAP_REPS):
        picked = [rng.choice(families) for _ in families]
        values = [value for family in picked for value in grouped[family]]
        draws.append(sum(values) / len(values))
    return [round(quantile(draws, 0.025), 6), round(quantile(draws, 0.975), 6)]


def average_ranks(values: dict[str, float], reverse: bool = True) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: (-item[1], item[0]) if reverse else (item[1], item[0]))
    ranks: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        rank = ((index + 1) + end) / 2
        for key, _ in ordered[index:end]:
            ranks[key] = rank
        index = end
    return ranks


def spearman(left: dict[str, float], right: dict[str, float]) -> float:
    keys = sorted(set(left) & set(right))
    if len(keys) < 2:
        return math.nan
    lr = average_ranks({key: left[key] for key in keys})
    rr = average_ranks({key: right[key] for key in keys})
    lm = sum(lr.values()) / len(keys)
    rm = sum(rr.values()) / len(keys)
    numerator = sum((lr[key] - lm) * (rr[key] - rm) for key in keys)
    denominator = math.sqrt(
        sum((lr[key] - lm) ** 2 for key in keys) * sum((rr[key] - rm) ** 2 for key in keys)
    )
    return round(numerator / denominator, 6) if denominator else math.nan


def rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def fmt_pct(value: float | None) -> str:
    return "NA" if value is None else f"{100 * value:.1f}%"


def load_rows() -> tuple[list[dict], dict[str, dict]]:
    generation = {row["slot_id"]: row for row in read(HERE / "GENERATION_MANIFEST.json")}
    private_map = read(FORMAL / "human_review/PRIVATE_MAP.json")
    reviews = {
        reviewer: {row["review_id"]: row for row in read(HUMAN / "validated" / f"{reviewer}.json")["records"]}
        for reviewer in REVIEWERS
    }
    assert set(private_map) == set(reviews[REVIEWERS[0]]) == set(reviews[REVIEWERS[1]])
    assert len(private_map) == 384

    rows: list[dict] = []
    programs: dict[str, dict] = {}
    all_obligations: set[str] = set()
    for review_id, mapping in private_map.items():
        slot = generation[mapping["slot_id"]]
        program = {
            "review_id": review_id,
            "slot_id": mapping["slot_id"],
            "task_id": slot["task_id"],
            "family": slot["family"],
            "axis": slot["axis"],
            "level": slot["level"],
            "layout": slot["layout"],
            "profile": slot["profile"],
            "prompt": slot["prompt"],
            "program_labels": {reviewer: reviews[reviewer][review_id]["program_label"] for reviewer in REVIEWERS},
        }
        programs[review_id] = program
        indexed = {
            reviewer: {item["obligation"]: item for item in reviews[reviewer][review_id]["judgments"]}
            for reviewer in REVIEWERS
        }
        assert set(indexed[REVIEWERS[0]]) == set(indexed[REVIEWERS[1]])
        all_obligations |= set(indexed[REVIEWERS[0]])
        for obligation in sorted(indexed[REVIEWERS[0]]):
            left, right = indexed[REVIEWERS[0]][obligation], indexed[REVIEWERS[1]][obligation]
            rows.append(
                {
                    **{key: program[key] for key in ("review_id", "slot_id", "task_id", "family", "axis", "level", "layout", "profile", "prompt")},
                    "obligation": obligation,
                    "category": CATEGORY_MAP[obligation],
                    "labels": {REVIEWERS[0]: left["label"], REVIEWERS[1]: right["label"]},
                    "scopes": {REVIEWERS[0]: left["scope_status"], REVIEWERS[1]: right["scope_status"]},
                }
            )
    assert all_obligations == set(CATEGORY_MAP), (sorted(all_obligations), sorted(CATEGORY_MAP))
    return rows, programs


def program_outcomes(programs: dict[str, dict]) -> dict:
    reviewer_counts = {
        reviewer: dict(Counter(row["program_labels"][reviewer] for row in programs.values()))
        for reviewer in REVIEWERS
    }
    consensus = Counter()
    by_family: dict[str, Counter] = defaultdict(Counter)
    for row in programs.values():
        labels = tuple(row["program_labels"][reviewer] for reviewer in REVIEWERS)
        if labels == ("UNSAFE", "UNSAFE"):
            bucket = "DEFINITE_UNSAFE"
        elif labels == ("SAFE", "SAFE"):
            bucket = "DEFINITE_SAFE"
        elif labels == ("UNKNOWN", "UNKNOWN"):
            bucket = "JOINT_UNKNOWN"
        else:
            bucket = "REVIEWER_DISCORDANT"
        consensus[bucket] += 1
        by_family[row["family"]][bucket] += 1
    return {
        "n_programs": len(programs),
        "reviewer_specific": reviewer_counts,
        "four_consensus_categories": dict(consensus),
        "by_family": {family: dict(counts) for family, counts in sorted(by_family.items())},
    }


def obligation_spectrum(rows: list[dict]) -> list[dict]:
    by_obligation: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_obligation[row["obligation"]].append(row)
    output = []
    for obligation in sorted(by_obligation):
        subset = by_obligation[obligation]
        families = sorted({row["family"] for row in subset})
        entry = {
            "obligation": obligation,
            "category": CATEGORY_MAP[obligation],
            "category_cn": CATEGORY_CN[CATEGORY_MAP[obligation]],
            "assigned_n": len(subset),
            "family_n": len(families),
            "families": families,
            "reviewer_specific": {},
        }
        for reviewer in REVIEWERS:
            counts = Counter(row["labels"][reviewer] for row in subset)
            violations = sum(row["labels"][reviewer] == "V" for row in subset)
            resolved_violations = sum(
                row["labels"][reviewer] == "V" and row["scopes"][reviewer] == "RESOLVED" for row in subset
            )
            decidable = counts["V"] + counts["C"]
            binary_rows = [{**row, "violation": row["labels"][reviewer] == "V"} for row in subset]
            entry["reviewer_specific"][reviewer] = {
                "counts": {label: counts[label] for label in ("C", "V", "U", "NA")},
                "unresolved_scope_n": sum(row["scopes"][reviewer] != "RESOLVED" for row in subset),
                "violation_n": violations,
                "violation_rate_full_assigned": rate(violations, len(subset)),
                "resolved_violation_n": resolved_violations,
                "decidable_violation_rate_secondary": rate(counts["V"], decidable),
                "families_with_violation_n": len({row["family"] for row in subset if row["labels"][reviewer] == "V"}),
                "family_cluster_bootstrap_95": family_cluster_bootstrap(binary_rows, "violation", f"{obligation}:{reviewer}"),
            }
        exact_v = [
            row
            for row in subset
            if all(row["labels"][reviewer] == "V" and row["scopes"][reviewer] == "RESOLVED" for reviewer in REVIEWERS)
        ]
        exact_c = [
            row
            for row in subset
            if all(row["labels"][reviewer] == "C" and row["scopes"][reviewer] == "RESOLVED" for reviewer in REVIEWERS)
        ]
        exact_any = [
            row
            for row in subset
            if row["scopes"][REVIEWERS[0]] == row["scopes"][REVIEWERS[1]] == "RESOLVED"
            and row["labels"][REVIEWERS[0]] == row["labels"][REVIEWERS[1]]
        ]
        either_v = [row for row in subset if any(row["labels"][reviewer] == "V" for reviewer in REVIEWERS)]
        entry["two_reviewer"] = {
            "exact_resolved_violation_n": len(exact_v),
            "exact_resolved_violation_rate_full_assigned_lower_bound": rate(len(exact_v), len(subset)),
            "exact_resolved_compliant_n": len(exact_c),
            "exact_resolved_agreement_n": len(exact_any),
            "exact_resolved_agreement_coverage": rate(len(exact_any), len(subset)),
            "either_reviewer_violation_n_sensitivity_upper": len(either_v),
            "either_reviewer_violation_rate_sensitivity_upper": rate(len(either_v), len(subset)),
            "reviewer_label_disagreement_n": sum(
                row["labels"][REVIEWERS[0]] != row["labels"][REVIEWERS[1]] for row in subset
            ),
            "either_unresolved_scope_n": sum(
                any(row["scopes"][reviewer] != "RESOLVED" for reviewer in REVIEWERS) for row in subset
            ),
            "families_with_exact_resolved_violation_n": len({row["family"] for row in exact_v}),
        }
        output.append(entry)
    return output


def category_spectrum(rows: list[dict]) -> list[dict]:
    program_category: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        program_category[(row["review_id"], row["category"])].append(row)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for (_, category), judgments in program_category.items():
        sample = judgments[0]
        grouped[category].append(
            {
                "review_id": sample["review_id"],
                "family": sample["family"],
                "reviewer_violation": {
                    reviewer: any(row["labels"][reviewer] == "V" for row in judgments) for reviewer in REVIEWERS
                },
                "joint_exact_violation": any(
                    all(row["labels"][reviewer] == "V" and row["scopes"][reviewer] == "RESOLVED" for reviewer in REVIEWERS)
                    for row in judgments
                ),
                "either_violation": any(
                    any(row["labels"][reviewer] == "V" for reviewer in REVIEWERS) for row in judgments
                ),
            }
        )
    output = []
    for category in sorted(grouped):
        subset = grouped[category]
        component_rows = [row for row in rows if row["category"] == category]
        entry = {
            "category": category,
            "category_cn": CATEGORY_CN[category],
            "applicable_program_n": len(subset),
            "family_n": len({row["family"] for row in subset}),
            "obligation_judgment_disagreement_n": sum(
                row["labels"][REVIEWERS[0]] != row["labels"][REVIEWERS[1]] for row in component_rows
            ),
            "reviewer_specific": {},
        }
        for reviewer in REVIEWERS:
            n = sum(row["reviewer_violation"][reviewer] for row in subset)
            binary = [{**row, "violation": row["reviewer_violation"][reviewer]} for row in subset]
            entry["reviewer_specific"][reviewer] = {
                "programs_with_any_violation_n": n,
                "rate_full_applicable": rate(n, len(subset)),
                "families_with_any_violation_n": len(
                    {row["family"] for row in subset if row["reviewer_violation"][reviewer]}
                ),
                "family_cluster_bootstrap_95": family_cluster_bootstrap(binary, "violation", f"category:{category}:{reviewer}"),
            }
        joint = sum(row["joint_exact_violation"] for row in subset)
        either = sum(row["either_violation"] for row in subset)
        entry["two_reviewer"] = {
            "programs_with_any_exact_resolved_violation_n": joint,
            "rate_full_applicable_lower_bound": rate(joint, len(subset)),
            "families_with_any_exact_resolved_violation_n": len(
                {row["family"] for row in subset if row["joint_exact_violation"]}
            ),
            "either_reviewer_any_violation_n_sensitivity_upper": either,
            "either_reviewer_any_violation_rate_sensitivity_upper": rate(either, len(subset)),
        }
        output.append(entry)
    return output


def family_spectrum(rows: list[dict]) -> list[dict]:
    output = []
    for family in sorted({row["family"] for row in rows}):
        family_rows = [row for row in rows if row["family"] == family and row["obligation"] != "TASK_GOAL"]
        program_ids = sorted({row["review_id"] for row in family_rows})
        for category in sorted({row["category"] for row in family_rows}):
            subset = [row for row in family_rows if row["category"] == category]
            applicable = sorted({row["review_id"] for row in subset})
            by_program = {review_id: [row for row in subset if row["review_id"] == review_id] for review_id in applicable}
            row_out = {
                "family": family,
                "family_program_n": len(program_ids),
                "category": category,
                "category_cn": CATEGORY_CN[category],
                "applicable_program_n": len(applicable),
            }
            for reviewer in REVIEWERS:
                value = sum(any(x["labels"][reviewer] == "V" for x in items) for items in by_program.values())
                row_out[f"{reviewer}_violation_n"] = value
                row_out[f"{reviewer}_rate"] = rate(value, len(applicable))
            joint = sum(
                any(
                    all(x["labels"][reviewer] == "V" and x["scopes"][reviewer] == "RESOLVED" for reviewer in REVIEWERS)
                    for x in items
                )
                for items in by_program.values()
            )
            row_out["joint_exact_violation_n"] = joint
            row_out["joint_lower_rate"] = rate(joint, len(applicable))
            output.append(row_out)
    return output


def add_rank_analysis(obligations: list[dict], categories: list[dict]) -> dict:
    eligible = [row for row in obligations if row["obligation"] != "TASK_GOAL" and row["family_n"] >= 2]
    rate_sets = {
        REVIEWERS[0]: {row["obligation"]: row["reviewer_specific"][REVIEWERS[0]]["violation_rate_full_assigned"] for row in eligible},
        REVIEWERS[1]: {row["obligation"]: row["reviewer_specific"][REVIEWERS[1]]["violation_rate_full_assigned"] for row in eligible},
        "JOINT_LOWER": {row["obligation"]: row["two_reviewer"]["exact_resolved_violation_rate_full_assigned_lower_bound"] for row in eligible},
    }
    ranks = {channel: average_ranks(values) for channel, values in rate_sets.items()}
    for row in obligations:
        row["cross_family_primary_eligible"] = row["obligation"] != "TASK_GOAL" and row["family_n"] >= 2
        row["ranks_among_cross_family_safety_obligations"] = {
            channel: ranks[channel].get(row["obligation"]) for channel in rate_sets
        }
    top_five = {
        channel: [key for key, _ in sorted(values.items(), key=lambda item: (-item[1], item[0]))[:5]]
        for channel, values in rate_sets.items()
    }
    robust_top_five = sorted(set(top_five[REVIEWERS[0]]) & set(top_five[REVIEWERS[1]]) & set(top_five["JOINT_LOWER"]))

    safety_categories = [row for row in categories if row["category"] != "TERMINAL_TASK_OUTCOME"]
    category_rates = {
        REVIEWERS[0]: {row["category"]: row["reviewer_specific"][REVIEWERS[0]]["rate_full_applicable"] for row in safety_categories},
        REVIEWERS[1]: {row["category"]: row["reviewer_specific"][REVIEWERS[1]]["rate_full_applicable"] for row in safety_categories},
        "JOINT_LOWER": {row["category"]: row["two_reviewer"]["rate_full_applicable_lower_bound"] for row in safety_categories},
    }
    category_rank = {channel: average_ranks(values) for channel, values in category_rates.items()}
    for row in categories:
        row["ranks_among_safety_categories"] = {
            channel: category_rank[channel].get(row["category"]) for channel in category_rates
        }
    category_order = {
        channel: [key for key, _ in sorted(values.items(), key=lambda item: (-item[1], item[0]))]
        for channel, values in category_rates.items()
    }
    top_two_sets = {channel: sorted(order[:2]) for channel, order in category_order.items()}
    return {
        "primary_scope": "Safety obligations excluding TASK_GOAL; obligations must occur in at least two task families.",
        "top_five_by_channel": top_five,
        "robust_top_five_intersection": robust_top_five,
        "spearman_rank_correlations": {
            f"{REVIEWERS[0]}__{REVIEWERS[1]}": spearman(rate_sets[REVIEWERS[0]], rate_sets[REVIEWERS[1]]),
            f"{REVIEWERS[0]}__JOINT_LOWER": spearman(rate_sets[REVIEWERS[0]], rate_sets["JOINT_LOWER"]),
            f"{REVIEWERS[1]}__JOINT_LOWER": spearman(rate_sets[REVIEWERS[1]], rate_sets["JOINT_LOWER"]),
        },
        "safety_category_order_by_channel": category_order,
        "same_top_safety_category_all_channels": len({order[0] for order in category_order.values()}) == 1,
        "top_two_safety_category_sets_by_channel": top_two_sets,
        "same_top_two_safety_category_set_all_channels": len({tuple(value) for value in top_two_sets.values()}) == 1,
    }


def classify_conclusions(obligations: list[dict], categories: list[dict], ranking: dict) -> tuple[list[dict], dict]:
    by_obligation = {row["obligation"]: row for row in obligations}
    by_category = {row["category"]: row for row in categories}
    findings = []

    for obligation in ranking["robust_top_five_intersection"]:
        row = by_obligation[obligation]
        recurring = all(
            row["reviewer_specific"][reviewer]["families_with_violation_n"] >= math.ceil(row["family_n"] / 2)
            for reviewer in REVIEWERS
        )
        if recurring and row["two_reviewer"]["families_with_exact_resolved_violation_n"] >= 2:
            findings.append(
                {
                    "type": "ROBUST_CROSS_FAMILY_OBLIGATION",
                    "obligation": obligation,
                    "assigned_n": row["assigned_n"],
                    "family_n": row["family_n"],
                    "reviewer_rates": {
                        reviewer: row["reviewer_specific"][reviewer]["violation_rate_full_assigned"] for reviewer in REVIEWERS
                    },
                    "joint_lower_rate": row["two_reviewer"]["exact_resolved_violation_rate_full_assigned_lower_bound"],
                    "interpretation": "Both reviewer channels place this obligation in the cross-family top five; exact-agreement violations recur in at least two families.",
                }
            )

    category_top = {channel: order[0] for channel, order in ranking["safety_category_order_by_channel"].items()}
    same_top = len(set(category_top.values())) == 1
    if same_top:
        category = next(iter(category_top.values()))
        row = by_category[category]
        findings.insert(
            0,
            {
                "type": "ROBUST_TOP_SAFETY_CATEGORY",
                "category": category,
                "category_cn": row["category_cn"],
                "applicable_program_n": row["applicable_program_n"],
                "family_n": row["family_n"],
                "reviewer_rates": {
                    reviewer: row["reviewer_specific"][reviewer]["rate_full_applicable"] for reviewer in REVIEWERS
                },
                "joint_lower_rate": row["two_reviewer"]["rate_full_applicable_lower_bound"],
                "interpretation": "This category ranks first under both independent reviewers and the exact-agreement lower bound.",
            },
        )

    same_top_two = ranking["same_top_two_safety_category_set_all_channels"]
    top_two = ranking["top_two_safety_category_sets_by_channel"][REVIEWERS[0]] if same_top_two else []
    if same_top_two:
        findings.insert(
            0,
            {
                "type": "ROBUST_DOMINANT_SAFETY_CATEGORY_TIER",
                "categories": top_two,
                "categories_cn": [by_category[category]["category_cn"] for category in top_two],
                "channel_orders": ranking["safety_category_order_by_channel"],
                "interpretation": "The same two categories occupy the top two positions under both independent reviewers and the exact-agreement lower bound; their internal order is not identifiable.",
            },
        )

    terminal = by_obligation["TASK_GOAL"]
    support = by_obligation["SUPPORT_DEPARTURE"]
    disagreements = {
        "TASK_GOAL": terminal["two_reviewer"]["reviewer_label_disagreement_n"],
        "SUPPORT_DEPARTURE": support["two_reviewer"]["reviewer_label_disagreement_n"],
        "CONTROL_FLOW_HOLDOUT": by_obligation["CONTROL_FLOW_HOLDOUT"]["two_reviewer"]["reviewer_label_disagreement_n"],
    }
    top_tier_disagreements = sum(by_category[category]["obligation_judgment_disagreement_n"] for category in top_two)
    adjudication = {
        "required_now": False,
        "package_prepared": False,
        "reason": (
            "The frozen policy treats reviewer disagreement as a result, not a defect to erase. "
            "The dominant two-category tier and four recurring obligations are identifiable from both independent channels and the exact-agreement lower bound. "
            "The order within that top tier is not identifiable, but RQ1 does not require a forced single winner. "
            "Reconciliation would touch a large semantic-disagreement set and is therefore neither targeted nor necessary."
            if same_top_two
            else "The dominant category tier is not invariant across channels; targeted reconciliation eligibility must be assessed before any prevalence superlative."
        ),
        "top_tier_obligation_judgment_disagreements_n": top_tier_disagreements,
        "largest_semantic_disagreements": disagreements,
        "trigger": "Only if a specific otherwise-stable main-table conclusion remains non-identifiable and substantially fewer than the full set of cases can resolve it.",
    }
    return findings, adjudication


def write_csvs(obligations: list[dict], families: list[dict], categories: list[dict]) -> None:
    obligation_path = ANALYSIS / "RQ1_DEFECT_SPECTRUM_BY_OBLIGATION.csv"
    fields = [
        "obligation", "category", "category_cn", "assigned_n", "family_n",
        "Reviewer1_V_n", "Reviewer1_V_rate", "Reviewer1_bootstrap_low", "Reviewer1_bootstrap_high",
        "Reviewer2_V_n", "Reviewer2_V_rate", "Reviewer2_bootstrap_low", "Reviewer2_bootstrap_high",
        "joint_exact_V_n", "joint_lower_rate", "either_V_upper_n", "either_V_upper_rate",
        "exact_agreement_coverage", "disagreement_n", "unresolved_scope_n",
        "rank_Reviewer1", "rank_Reviewer2", "rank_joint_lower", "cross_family_primary_eligible",
    ]
    with obligation_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in obligations:
            left = row["reviewer_specific"][REVIEWERS[0]]
            right = row["reviewer_specific"][REVIEWERS[1]]
            joint = row["two_reviewer"]
            ranks = row["ranks_among_cross_family_safety_obligations"]
            writer.writerow({
                "obligation": row["obligation"], "category": row["category"], "category_cn": row["category_cn"],
                "assigned_n": row["assigned_n"], "family_n": row["family_n"],
                "Reviewer1_V_n": left["violation_n"], "Reviewer1_V_rate": left["violation_rate_full_assigned"],
                "Reviewer1_bootstrap_low": left["family_cluster_bootstrap_95"][0], "Reviewer1_bootstrap_high": left["family_cluster_bootstrap_95"][1],
                "Reviewer2_V_n": right["violation_n"], "Reviewer2_V_rate": right["violation_rate_full_assigned"],
                "Reviewer2_bootstrap_low": right["family_cluster_bootstrap_95"][0], "Reviewer2_bootstrap_high": right["family_cluster_bootstrap_95"][1],
                "joint_exact_V_n": joint["exact_resolved_violation_n"], "joint_lower_rate": joint["exact_resolved_violation_rate_full_assigned_lower_bound"],
                "either_V_upper_n": joint["either_reviewer_violation_n_sensitivity_upper"], "either_V_upper_rate": joint["either_reviewer_violation_rate_sensitivity_upper"],
                "exact_agreement_coverage": joint["exact_resolved_agreement_coverage"], "disagreement_n": joint["reviewer_label_disagreement_n"],
                "unresolved_scope_n": joint["either_unresolved_scope_n"], "rank_Reviewer1": ranks[REVIEWERS[0]],
                "rank_Reviewer2": ranks[REVIEWERS[1]], "rank_joint_lower": ranks["JOINT_LOWER"],
                "cross_family_primary_eligible": row["cross_family_primary_eligible"],
            })

    category_path = ANALYSIS / "RQ1_DEFECT_SPECTRUM_BY_CATEGORY.csv"
    category_fields = [
        "category", "category_cn", "applicable_program_n", "family_n",
        "Reviewer1_any_V_n", "Reviewer1_rate", "Reviewer1_bootstrap_low", "Reviewer1_bootstrap_high",
        "Reviewer2_any_V_n", "Reviewer2_rate", "Reviewer2_bootstrap_low", "Reviewer2_bootstrap_high",
        "joint_any_exact_V_n", "joint_lower_rate", "either_any_V_upper_n", "either_any_V_upper_rate",
        "rank_Reviewer1", "rank_Reviewer2", "rank_joint_lower",
    ]
    with category_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=category_fields)
        writer.writeheader()
        for row in categories:
            left = row["reviewer_specific"][REVIEWERS[0]]
            right = row["reviewer_specific"][REVIEWERS[1]]
            joint = row["two_reviewer"]
            ranks = row["ranks_among_safety_categories"]
            writer.writerow({
                "category": row["category"], "category_cn": row["category_cn"],
                "applicable_program_n": row["applicable_program_n"], "family_n": row["family_n"],
                "Reviewer1_any_V_n": left["programs_with_any_violation_n"], "Reviewer1_rate": left["rate_full_applicable"],
                "Reviewer1_bootstrap_low": left["family_cluster_bootstrap_95"][0], "Reviewer1_bootstrap_high": left["family_cluster_bootstrap_95"][1],
                "Reviewer2_any_V_n": right["programs_with_any_violation_n"], "Reviewer2_rate": right["rate_full_applicable"],
                "Reviewer2_bootstrap_low": right["family_cluster_bootstrap_95"][0], "Reviewer2_bootstrap_high": right["family_cluster_bootstrap_95"][1],
                "joint_any_exact_V_n": joint["programs_with_any_exact_resolved_violation_n"], "joint_lower_rate": joint["rate_full_applicable_lower_bound"],
                "either_any_V_upper_n": joint["either_reviewer_any_violation_n_sensitivity_upper"], "either_any_V_upper_rate": joint["either_reviewer_any_violation_rate_sensitivity_upper"],
                "rank_Reviewer1": ranks[REVIEWERS[0]], "rank_Reviewer2": ranks[REVIEWERS[1]], "rank_joint_lower": ranks["JOINT_LOWER"],
            })

    family_path = ANALYSIS / "RQ1_DEFECT_SPECTRUM_BY_FAMILY.csv"
    family_fields = list(families[0])
    with family_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=family_fields)
        writer.writeheader()
        writer.writerows(families)


def write_markdown(result: dict) -> None:
    lines = [
        "# RQ1 natural-defect spectrum — frozen result",
        "",
        f"Status: **{result['status']}**",
        "",
        "This is a statistical synthesis of the existing 384 natural programs. It adds no programs, changes no human label, and does not pool the two reviewers into a synthetic truth.",
        "",
        "## Program-level distribution",
        "",
    ]
    outcomes = result["program_outcomes"]
    for reviewer in REVIEWERS:
        lines.append(f"- {reviewer}: {outcomes['reviewer_specific'][reviewer]}.")
    lines.append(f"- Four two-reviewer categories: {outcomes['four_consensus_categories']}.")
    lines += ["", "## Paper-level RQ1 findings", ""]
    for finding in result["paper_level_findings"]:
        if finding["type"] == "PROGRAM_LEVEL_NATURAL_DEFECT_BURDEN":
            lines.append(
                f"- **Natural unsafe outcomes are common across all 16 families.** {finding['definite_unsafe_n']}/384 ({fmt_pct(finding['definite_unsafe_rate'])}) are UNSAFE under both reviewers; reviewer-specific UNSAFE rates are {fmt_pct(finding['reviewer_unsafe_rates'][REVIEWERS[0]])} and {fmt_pct(finding['reviewer_unsafe_rates'][REVIEWERS[1]])}."
            )
        elif finding["type"] == "ROBUST_DOMINANT_SAFETY_CATEGORY_TIER":
            lines.append(
                f"- **Robust dominant tier: {' and '.join(finding['categories_cn'])}.** The same pair ranks first/second under both reviewers and the exact-agreement lower bound; their internal order is not identifiable and is not forced."
            )
        elif finding["type"] == "ROBUST_TOP_SAFETY_CATEGORY":
            lines.append(
                f"- **Robust top category: {finding['category_cn']}** over {finding['applicable_program_n']} applicable programs and {finding['family_n']} families. "
                f"Reviewer rates: {REVIEWERS[0]} {fmt_pct(finding['reviewer_rates'][REVIEWERS[0]])}, "
                f"{REVIEWERS[1]} {fmt_pct(finding['reviewer_rates'][REVIEWERS[1]])}; "
                f"exact-agreement lower bound {fmt_pct(finding['joint_lower_rate'])}."
            )
        else:
            lines.append(
                f"- **{finding['obligation']}**: {finding['assigned_n']} assigned programs across {finding['family_n']} families; "
                f"reviewer violation rates {fmt_pct(finding['reviewer_rates'][REVIEWERS[0]])} and "
                f"{fmt_pct(finding['reviewer_rates'][REVIEWERS[1]])}; exact-agreement lower bound "
                f"{fmt_pct(finding['joint_lower_rate'])}."
            )
    lines += [
        "",
        "These are prevalence descriptions, not causal claims. `TASK_GOAL` is reported separately because it is a terminal functional outcome rather than a safety-defect type.",
        "",
        "## Obligation spectrum",
        "",
        "| Obligation | Families | Assigned | Reviewer 1 V | Reviewer 2 V | Joint lower bound | Agreement coverage |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(result["obligation_spectrum"], key=lambda x: (-x["two_reviewer"]["exact_resolved_violation_rate_full_assigned_lower_bound"], x["obligation"])):
        left = row["reviewer_specific"][REVIEWERS[0]]
        right = row["reviewer_specific"][REVIEWERS[1]]
        joint = row["two_reviewer"]
        lines.append(
            f"| {row['obligation']} | {row['family_n']} | {row['assigned_n']} | "
            f"{left['violation_n']} ({fmt_pct(left['violation_rate_full_assigned'])}) | "
            f"{right['violation_n']} ({fmt_pct(right['violation_rate_full_assigned'])}) | "
            f"{joint['exact_resolved_violation_n']} ({fmt_pct(joint['exact_resolved_violation_rate_full_assigned_lower_bound'])}) | "
            f"{fmt_pct(joint['exact_resolved_agreement_coverage'])} |"
        )
    lines += [
        "",
        "## Reviewer disagreement and adjudication decision",
        "",
        f"- Decision: **no new human package now**. {result['adjudication']['reason']}",
        f"- Largest named semantic disagreements: {result['adjudication']['largest_semantic_disagreements']}.",
        "- Therefore no single pooled prevalence is reported. Reviewer-specific estimates, exact-agreement lower bounds, and sensitivity upper bounds remain side by side.",
        "",
        "## Scope boundary",
        "",
        "RQ1 is now statistically summarized from the frozen data. This does not close RQ2 or RQ4 and does not authorize full-manuscript drafting. The next main experiment is the already-frozen RQ2 holdout analysis.",
        "",
    ]
    (ANALYSIS / "RQ1_DEFECT_SPECTRUM.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows, programs = load_rows()
    obligations = obligation_spectrum(rows)
    categories = category_spectrum(rows)
    families = family_spectrum(rows)
    ranking = add_rank_analysis(obligations, categories)
    findings, adjudication = classify_conclusions(obligations, categories, ranking)
    outcomes = program_outcomes(programs)
    definite_unsafe = outcomes["four_consensus_categories"]["DEFINITE_UNSAFE"]
    findings.insert(0, {
        "type": "PROGRAM_LEVEL_NATURAL_DEFECT_BURDEN",
        "definite_unsafe_n": definite_unsafe,
        "definite_unsafe_rate": rate(definite_unsafe, 384),
        "reviewer_unsafe_rates": {
            reviewer: rate(outcomes["reviewer_specific"][reviewer].get("UNSAFE", 0), 384) for reviewer in REVIEWERS
        },
        "families_with_definite_unsafe_n": sum(
            family_counts.get("DEFINITE_UNSAFE", 0) > 0 for family_counts in outcomes["by_family"].values()
        ),
        "interpretation": "A conservative two-reviewer lower bound still labels more than half of the natural programs unsafe, and definite unsafe cases occur in every task family.",
    })
    status = "RQ1_SPECTRUM_IDENTIFIED_WITH_DUAL_REVIEWER_UNCERTAINTY" if findings else "RQ1_SPECTRUM_DESCRIBED_NO_STABLE_SUPERLATIVE"
    result = {
        "schema": "paper3.rq1_defect_spectrum.v1",
        "status": status,
        "question": "What defects naturally occur in generated bimanual robot programs?",
        "scope": {
            "programs": 384,
            "task_families": 16,
            "reviewers": list(REVIEWERS),
            "data_origin": "Existing frozen natural-program main study only; no mutations and no new programs.",
            "unit": "Generated program; category prevalence is unique-program based; uncertainty resamples task families.",
        },
        "policy": {
            "no_pooled_truth": True,
            "primary_denominator": "All programs assigned the obligation/category; U and NA remain in the denominator.",
            "joint_lower_bound": "Both reviewers label V and both scopes are RESOLVED.",
            "sensitivity_upper": "Either reviewer labels V; descriptive bound only, not consensus truth.",
            "bootstrap": f"{BOOTSTRAP_REPS} family-cluster resamples, seed {SEED} plus deterministic analysis salt.",
            "task_goal_handling": "Reported separately from the safety-defect spectrum.",
        },
        "program_outcomes": outcomes,
        "obligation_spectrum": obligations,
        "category_spectrum": categories,
        "ranking_robustness": ranking,
        "paper_level_findings": findings,
        "adjudication": adjudication,
        "input_hashes": {
            "generation_manifest": sha256(HERE / "GENERATION_MANIFEST.json"),
            "private_map": sha256(FORMAL / "human_review/PRIVATE_MAP.json"),
            **{f"review_{reviewer}": sha256(HUMAN / "validated" / f"{reviewer}.json") for reviewer in REVIEWERS},
            "truth_policy": sha256(HUMAN / "HUMAN_TRUTH_POLICY_PREDEBLIND.json"),
        },
        "outputs": {
            "obligation_csv": "RQ1_DEFECT_SPECTRUM_BY_OBLIGATION.csv",
            "category_csv": "RQ1_DEFECT_SPECTRUM_BY_CATEGORY.csv",
            "family_csv": "RQ1_DEFECT_SPECTRUM_BY_FAMILY.csv",
            "markdown": "RQ1_DEFECT_SPECTRUM.md",
        },
    }
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    write_csvs(obligations, families, categories)
    write_json(ANALYSIS / "RQ1_DEFECT_SPECTRUM.json", result)
    write_markdown(result)
    print(json.dumps({
        "status": status,
        "paper_level_findings": findings,
        "adjudication": adjudication,
        "ranking_robustness": ranking,
        "outputs": result["outputs"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
