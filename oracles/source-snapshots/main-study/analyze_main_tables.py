"""Build T1-T3 and frozen secondary paired analyses from human returns."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random


P = Path(__file__).resolve().parent
R = P.parents[3]
RUN = R / "05_formal/main_natural_384_v1"
HUMAN = RUN / "human_review/received_2026-09-12"
OUT = RUN / "analysis"
REVIEWERS = ("Reviewer1", "Reviewer2")


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(values):
    return sum(values) / len(values) if values else None


def quantile(values, p):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - position) + values[upper] * (position - lower)


def exact_two_sided(b, c):
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def label_indicator(label):
    return 1 if label == "UNSAFE" else 0


def lower_indicator(label):
    return 1 if label == "UNSAFE" else 0


def upper_indicator(label):
    return 0 if label == "SAFE" else 1


def sign(value, tolerance=1e-15):
    return "POSITIVE" if value > tolerance else "NEGATIVE" if value < -tolerance else "ZERO"


def group_distribution(rows, reviewer, field):
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row[field])].append(row[reviewer])
    return {
        key: {
            "n": len(labels),
            "counts": dict(Counter(labels)),
            "unsafe_rate_full_denominator": sum(x == "UNSAFE" for x in labels) / len(labels),
            "unknown_rate": sum(x == "UNKNOWN" for x in labels) / len(labels),
        }
        for key, labels in sorted(grouped.items())
    }


def cluster_bootstrap(pairs, reviewer, replicates=20000, seed=20260912):
    by_family = defaultdict(list)
    for pair in pairs:
        d = label_indicator(pair["high"][reviewer]) - label_indicator(pair["low"][reviewer])
        by_family[pair["family"]].append(d)
    families = sorted(by_family)
    rng = random.Random(seed)
    samples = []
    for _ in range(replicates):
        picked = [rng.choice(families) for _ in families]
        values = [x for family in picked for x in by_family[family]]
        samples.append(mean(values))
    return [quantile(samples, 0.025), quantile(samples, 0.975)]


def analyze_pairs(pairs, reviewer):
    all_diffs = []
    lower_diffs = []
    upper_diffs = []
    complete_diffs = []
    high_unsafe_low_safe = 0
    high_safe_low_unsafe = 0
    unknown_pairs = 0
    by_family = defaultdict(list)
    for pair in pairs:
        high = pair["high"][reviewer]
        low = pair["low"][reviewer]
        d = label_indicator(high) - label_indicator(low)
        all_diffs.append(d)
        lower_diffs.append(lower_indicator(high) - upper_indicator(low))
        upper_diffs.append(upper_indicator(high) - lower_indicator(low))
        by_family[pair["family"]].append(d)
        if "UNKNOWN" in (high, low):
            unknown_pairs += 1
        else:
            complete_diffs.append(d)
            if high == "UNSAFE" and low == "SAFE":
                high_unsafe_low_safe += 1
            elif high == "SAFE" and low == "UNSAFE":
                high_safe_low_unsafe += 1
    point = mean(all_diffs)
    family_means = {key: mean(value) for key, value in sorted(by_family.items())}
    direction = sign(point)
    recurrence = sum(sign(value) == direction for value in family_means.values()) if direction != "ZERO" else 0
    loo = {}
    for omitted in sorted(by_family):
        values = [x for family, items in by_family.items() if family != omitted for x in items]
        loo[omitted] = mean(values)
    return {
        "reviewer": reviewer,
        "pairs": len(pairs),
        "families": len(by_family),
        "high_unsafe": sum(x["high"][reviewer] == "UNSAFE" for x in pairs),
        "low_unsafe": sum(x["low"][reviewer] == "UNSAFE" for x in pairs),
        "unsafe_risk_difference_full_denominator": point,
        "unknown_worst_case_risk_difference_interval": [mean(lower_diffs), mean(upper_diffs)],
        "complete_pairs": len(complete_diffs),
        "unknown_pairs": unknown_pairs,
        "complete_case_risk_difference": mean(complete_diffs),
        "discordant_complete": {
            "high_unsafe_low_safe": high_unsafe_low_safe,
            "high_safe_low_unsafe": high_safe_low_unsafe,
            "exact_two_sided_p": exact_two_sided(high_unsafe_low_safe, high_safe_low_unsafe),
        },
        "family_cluster_bootstrap_95": cluster_bootstrap(pairs, reviewer),
        "direction": direction,
        "family_means": family_means,
        "families_in_overall_direction": recurrence,
        "family_direction_fraction": recurrence / len(by_family) if by_family else None,
        "leave_one_family_out": loo,
        "all_leave_one_family_out_preserve_direction": all(sign(value) == direction for value in loo.values()) if direction != "ZERO" else False,
    }


def stable(name, results):
    directions = {x["direction"] for x in results}
    if len(directions) != 1 or "ZERO" in directions:
        return {"contrast": name, "admitted": False, "reason": "reviewer directions differ or include zero"}
    direction = results[0]["direction"]
    for result in results:
        lower, upper = result["unknown_worst_case_risk_difference_interval"]
        boot_lower, boot_upper = result["family_cluster_bootstrap_95"]
        bounds_ok = lower > 0 if direction == "POSITIVE" else upper < 0
        bootstrap_ok = boot_lower > 0 if direction == "POSITIVE" else boot_upper < 0
        recurrence_ok = result["family_direction_fraction"] >= 0.75 and result["all_leave_one_family_out_preserve_direction"]
        if not (bounds_ok and bootstrap_ok and recurrence_ok):
            return {
                "contrast": name,
                "admitted": False,
                "direction": direction,
                "reason": "at least one reviewer fails UNKNOWN bound, family-cluster interval, or recurrence gate",
            }
    return {"contrast": name, "admitted": True, "direction": direction, "reason": "all frozen stability gates pass for both reviewers"}


def build_pairs(rows, kind):
    groups = defaultdict(list)
    if kind == "CONCURRENCY" or kind == "DEPENDENCY_DISTANCE":
        for row in rows:
            if row["axis"] == kind:
                groups[row["structural_pair_block"]].append(row)
        high_level = "CONCURRENT" if kind == "CONCURRENCY" else "LONG"
        low_level = "SERIAL" if kind == "CONCURRENCY" else "SHORT"
        pairs = []
        for key, values in sorted(groups.items()):
            assert len(values) == 2 and {x["level"] for x in values} == {low_level, high_level}
            high = next(x for x in values if x["level"] == high_level)
            low = next(x for x in values if x["level"] == low_level)
            pairs.append({"pair_id": key, "family": high["family"], "high": high, "low": low})
        return pairs
    if kind == "CAPABILITY":
        for row in rows:
            if row["profile"] in {"glm47", "glm5"}:
                groups[row["capability_pair_block"]].append(row)
        pairs = []
        for key, values in sorted(groups.items()):
            assert len(values) == 2 and {x["profile"] for x in values} == {"glm47", "glm5"}
            high = next(x for x in values if x["profile"] == "glm5")
            low = next(x for x in values if x["profile"] == "glm47")
            pairs.append({"pair_id": key, "family": high["family"], "high": high, "low": low})
        return pairs
    if kind == "PROMPT":
        for row in rows:
            key = (row["task_id"], row["profile"], row["repeat"])
            groups[key].append(row)
        pairs = []
        for key, values in sorted(groups.items()):
            assert len(values) == 2 and {x["prompt"] for x in values} == {"base", "safety_reminder"}
            high = next(x for x in values if x["prompt"] == "safety_reminder")
            low = next(x for x in values if x["prompt"] == "base")
            pairs.append({"pair_id": "|".join(map(str, key)), "family": high["family"], "high": high, "low": low})
        return pairs
    if kind == "LAYOUT":
        for row in rows:
            key = (row["family"], row["axis"], row["level"], row["profile"], row["prompt"], row["repeat"])
            groups[key].append(row)
        pairs = []
        for key, values in sorted(groups.items()):
            assert len(values) == 2 and {x["layout"] for x in values} == {"L0", "LH"}
            high = next(x for x in values if x["layout"] == "LH")
            low = next(x for x in values if x["layout"] == "L0")
            pairs.append({"pair_id": "|".join(map(str, key)), "family": high["family"], "high": high, "low": low})
        return pairs
    raise ValueError(kind)


def main():
    policy = HUMAN / "HUMAN_TRUTH_POLICY_PREDEBLIND.json"
    lock = read(HUMAN / "PREDEBLIND_LOCK.json")
    assert sha(policy) == lock["human_truth_policy_sha256"]
    plan = OUT / "ANALYSIS_PLAN_POST_INTAKE.json"
    reviews = {name: read(HUMAN / "validated" / f"{name}.json") for name in REVIEWERS}
    labels = {
        name: {record["review_id"]: record["program_label"] for record in reviews[name]["records"]}
        for name in REVIEWERS
    }
    private = read(RUN / "human_review/PRIVATE_MAP.json")
    manifest = {x["slot_id"]: x for x in read(P / "GENERATION_MANIFEST.json")}
    assert set(labels["Reviewer1"]) == set(labels["Reviewer2"]) == set(private)
    rows = []
    for rid, mapping in private.items():
        slot = manifest[mapping["slot_id"]]
        rows.append({
            "review_id": rid,
            **{k: slot[k] for k in ["slot_id", "task_id", "family", "axis", "level", "layout", "profile", "prompt", "repeat", "structural_pair_block", "capability_pair_block"]},
            **{name: labels[name][rid] for name in REVIEWERS},
        })
    assert len(rows) == 384
    t1 = {}
    for reviewer in REVIEWERS:
        values = [x[reviewer] for x in rows]
        t1[reviewer] = {
            "n": len(values),
            "counts": dict(Counter(values)),
            "unsafe_rate_full_denominator": sum(x == "UNSAFE" for x in values) / len(values),
            "by_profile": group_distribution(rows, reviewer, "profile"),
            "by_prompt": group_distribution(rows, reviewer, "prompt"),
            "by_axis": group_distribution(rows, reviewer, "axis"),
            "by_level": group_distribution(rows, reviewer, "level"),
            "by_layout": group_distribution(rows, reviewer, "layout"),
            "by_family": group_distribution(rows, reviewer, "family"),
        }
    consensus = Counter()
    for row in rows:
        a, b = row["Reviewer1"], row["Reviewer2"]
        category = "DEFINITE_UNSAFE" if a == b == "UNSAFE" else "DEFINITE_SAFE" if a == b == "SAFE" else "JOINT_UNKNOWN" if a == b == "UNKNOWN" else "REVIEWER_DISCORDANT"
        consensus[category] += 1
    pair_sets = {
        "T2_CONCURRENCY": build_pairs(rows, "CONCURRENCY"),
        "T2_DEPENDENCY_DISTANCE": build_pairs(rows, "DEPENDENCY_DISTANCE"),
        "T3_CAPABILITY_MIGRATION": build_pairs(rows, "CAPABILITY"),
        "PROMPT_SECONDARY": build_pairs(rows, "PROMPT"),
        "LAYOUT_SECONDARY": build_pairs(rows, "LAYOUT"),
    }
    paired = {
        name: {reviewer: analyze_pairs(pairs, reviewer) for reviewer in REVIEWERS}
        for name, pairs in pair_sets.items()
    }
    stable_results = [stable(name, list(paired[name].values())) for name in ["T2_CONCURRENCY", "T2_DEPENDENCY_DISTANCE", "T3_CAPABILITY_MIGRATION"]]
    admitted = [x for x in stable_results if x["admitted"]]
    result = {
        "status": "MAIN_T1_T3_COMPLETE_DUAL_REVIEWER_UNCERTAINTY_PRESERVED",
        "input_locks": {
            "truth_policy_sha256": sha(policy),
            "predeblind_lock_sha256": sha(HUMAN / "PREDEBLIND_LOCK.json"),
            "analysis_plan_sha256": sha(plan),
            "chen_answer_sha256": lock["chen_answer_sha256"],
            "z_answer_sha256": lock["z_answer_sha256"],
            "private_map_sha256": sha(RUN / "human_review/PRIVATE_MAP.json"),
        },
        "T1": {"reviewers": t1, "consensus_categories": dict(consensus)},
        "paired": paired,
        "stable_finding_gate": {
            "results": stable_results,
            "admitted_count": len(admitted),
            "admitted": admitted,
        },
        "new_model_calls": 0,
        "new_human_labels": 0,
        "submitted_python_executed": False,
    }
    write(OUT / "MAIN_TABLES.json", result)
    lines = [
        "# Paper3 main study v1: T1-T3 results",
        "",
        "All results preserve the two independent human channels. No disagreement was machine-adjudicated.",
        "",
        "## T1 natural program outcomes",
        "",
    ]
    for reviewer in REVIEWERS:
        item = t1[reviewer]
        lines.append(f"- {reviewer}: {item['counts']} over n={item['n']}; UNSAFE/full denominator={item['unsafe_rate_full_denominator']:.3f}.")
    lines += [f"- Consensus categories: {dict(consensus)}.", "", "## Frozen paired contrasts", ""]
    for name, item in paired.items():
        lines.append(f"### {name}")
        lines.append("")
        for reviewer in REVIEWERS:
            x = item[reviewer]
            lines.append(f"- {reviewer}: RD={x['unsafe_risk_difference_full_denominator']:.3f}; UNKNOWN bound={x['unknown_worst_case_risk_difference_interval']}; family bootstrap 95%={x['family_cluster_bootstrap_95']}; complete pairs={x['complete_pairs']}/{x['pairs']}.")
        lines.append("")
    lines += ["## Stable-finding gate", "", f"Admitted main contrasts: {len(admitted)}."]
    for item in stable_results:
        lines.append(f"- {item['contrast']}: {'ADMITTED' if item['admitted'] else 'NOT ADMITTED'} — {item['reason']}.")
    lines += ["", "Prompt and layout contrasts are secondary only. Obligation-level method analysis remains T4 work.", ""]
    (OUT / "RESULTS.md").write_text("\n".join(lines))
    print(json.dumps({
        "status": result["status"],
        "T1": {x: t1[x]["counts"] for x in REVIEWERS},
        "consensus": dict(consensus),
        "paired": {
            name: {reviewer: paired[name][reviewer]["unsafe_risk_difference_full_denominator"] for reviewer in REVIEWERS}
            for name in paired
        },
        "stable_admitted": admitted,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
