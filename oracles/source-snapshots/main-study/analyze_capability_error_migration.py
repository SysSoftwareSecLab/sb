"""Secondary obligation-level decomposition of the frozen GLM-4.7/GLM-5 pairs.

This reuses the 128 existing capability pairs and two independent human reviews.
It makes no model calls, adds no labels, and does not alter the preregistered T3
program-level result.  The output is a paper-facing mechanism decomposition of
mentor RQ4: whether capability improvement changes which safety obligations fail.
"""

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random


P = Path(__file__).resolve().parent
R = P.parents[3]
RUN = R / "05_formal/main_natural_384_v1"
HUMAN = RUN / "human_review/received_2026-09-12/validated"
OUT = RUN / "analysis"
REVIEWERS = ("Reviewer1", "Reviewer2")


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def effective(judgment):
    if judgment["scope_status"] != "RESOLVED":
        return "U_SCOPE"
    return judgment["label"]


def bounds(label):
    if label == "V":
        return (1, 1)
    if label == "C":
        return (0, 0)
    return (0, 1)


def bootstrap(rows, replicates=10000, seed=20260912):
    by_family = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row["point_difference"])
    families = sorted(by_family)
    rng = random.Random(seed)
    samples = []
    for _ in range(replicates):
        picked = [rng.choice(families) for _ in families]
        values = [value for family in picked for value in by_family[family]]
        samples.append(sum(values) / len(values))
    return [quantile(samples, 0.025), quantile(samples, 0.975)]


def summarize(rows):
    n = len(rows)
    low_v = sum(row["low_label"] == "V" for row in rows)
    high_v = sum(row["high_label"] == "V" for row in rows)
    lower = sum(row["lower_difference"] for row in rows) / n
    upper = sum(row["upper_difference"] for row in rows) / n
    return {
        "obligation_pairs": n,
        "families": len({row["family"] for row in rows}),
        "glm47_v": low_v,
        "glm5_v": high_v,
        "glm47_v_rate_full_denominator": low_v / n,
        "glm5_v_rate_full_denominator": high_v / n,
        "glm5_minus_glm47_v_risk_difference": (high_v - low_v) / n,
        "unknown_worst_case_risk_difference_interval": [lower, upper],
        "family_cluster_bootstrap_95_point_indicator": bootstrap(rows),
        "transition_counts": dict(Counter(f'{row["low_label"]}->{row["high_label"]}' for row in rows)),
    }


def main():
    manifest = {row["slot_id"]: row for row in read(P / "GENERATION_MANIFEST.json")}
    private = read(RUN / "human_review/PRIVATE_MAP.json")
    reviews = {}
    for reviewer in REVIEWERS:
        payload = read(HUMAN / f"{reviewer}.json")
        reviews[reviewer] = {record["review_id"]: record for record in payload["records"]}
    assert set(private) == set(reviews[REVIEWERS[0]]) == set(reviews[REVIEWERS[1]])

    slots = {}
    for review_id, mapping in private.items():
        slot = dict(manifest[mapping["slot_id"]])
        slot["review_id"] = review_id
        slot["reviews"] = {
            reviewer: {
                judgment["obligation"]: judgment
                for judgment in reviews[reviewer][review_id]["judgments"]
            }
            for reviewer in REVIEWERS
        }
        slots[slot["slot_id"]] = slot

    grouped = defaultdict(list)
    for slot in slots.values():
        if slot["profile"] in {"glm47", "glm5"}:
            grouped[slot["capability_pair_block"]].append(slot)
    pairs = []
    for pair_id, values in sorted(grouped.items()):
        assert len(values) == 2 and {row["profile"] for row in values} == {"glm47", "glm5"}
        low = next(row for row in values if row["profile"] == "glm47")
        high = next(row for row in values if row["profile"] == "glm5")
        for reviewer in REVIEWERS:
            assert set(low["reviews"][reviewer]) == set(high["reviews"][reviewer])
        pairs.append({"pair_id": pair_id, "family": high["family"], "low": low, "high": high})
    assert len(pairs) == 128

    reviewer_results = {}
    reviewer_rows = {}
    for reviewer in REVIEWERS:
        rows = []
        for pair in pairs:
            obligations = sorted(pair["low"]["reviews"][reviewer])
            for obligation in obligations:
                low_j = pair["low"]["reviews"][reviewer][obligation]
                high_j = pair["high"]["reviews"][reviewer][obligation]
                low_label = effective(low_j)
                high_label = effective(high_j)
                low_lower, low_upper = bounds(low_label)
                high_lower, high_upper = bounds(high_label)
                rows.append({
                    "pair_id": pair["pair_id"],
                    "family": pair["family"],
                    "obligation": obligation,
                    "low_label": low_label,
                    "high_label": high_label,
                    "point_difference": int(high_label == "V") - int(low_label == "V"),
                    "lower_difference": high_lower - low_upper,
                    "upper_difference": high_upper - low_lower,
                })
        reviewer_rows[reviewer] = rows
        by_obligation = defaultdict(list)
        for row in rows:
            by_obligation[row["obligation"]].append(row)
        reviewer_results[reviewer] = {
            "overall": summarize(rows),
            "by_obligation": {
                obligation: summarize(values)
                for obligation, values in sorted(by_obligation.items())
            },
        }

    exact_rows = []
    for pair in pairs:
        obligation_sets = [set(pair[side]["reviews"][reviewer]) for side in ("low", "high") for reviewer in REVIEWERS]
        obligations = sorted(set.intersection(*obligation_sets))
        for obligation in obligations:
            labels = {}
            admitted = True
            for side in ("low", "high"):
                judgments = [pair[side]["reviews"][reviewer][obligation] for reviewer in REVIEWERS]
                if not all(j["scope_status"] == "RESOLVED" for j in judgments):
                    admitted = False
                    break
                if judgments[0]["label"] != judgments[1]["label"]:
                    admitted = False
                    break
                labels[side] = judgments[0]["label"]
            if admitted:
                exact_rows.append({
                    "pair_id": pair["pair_id"],
                    "family": pair["family"],
                    "obligation": obligation,
                    "low_label": labels["low"],
                    "high_label": labels["high"],
                })

    exact_decidable = [row for row in exact_rows if row["low_label"] in {"C", "V"} and row["high_label"] in {"C", "V"}]
    exact_by_obligation = defaultdict(list)
    for row in exact_decidable:
        exact_by_obligation[row["obligation"]].append(row)

    result = {
        "status": "SECONDARY_RQ4_OBLIGATION_MIGRATION_COMPLETE",
        "analysis_role": "post-hoc secondary mechanism decomposition; does not replace the frozen program-level T3 gate",
        "question": "When capability rises from GLM-4.7 to GLM-5 on matched tasks, which safety-obligation errors appear, disappear, or remain?",
        "design": {
            "capability_pairs": len(pairs),
            "families": len({pair["family"] for pair in pairs}),
            "pairing": "same task, prompt, repeat, and layout; GLM-5 minus GLM-4.7",
            "human_channels": list(REVIEWERS),
            "unknown_policy": "U, NA, and unresolved scope are unknown; point estimate counts only V; interval assigns unknown adversarially",
        },
        "reviewer_channels": reviewer_results,
        "two_reviewer_exact_resolved": {
            "all_labels_pairs": len(exact_rows),
            "all_labels_transition_counts": dict(Counter(f'{row["low_label"]}->{row["high_label"]}' for row in exact_rows)),
            "decidable_c_or_v_pairs": len(exact_decidable),
            "decidable_transition_counts": dict(Counter(f'{row["low_label"]}->{row["high_label"]}' for row in exact_decidable)),
            "by_obligation": {
                obligation: {
                    "n": len(values),
                    "transition_counts": dict(Counter(f'{row["low_label"]}->{row["high_label"]}' for row in values)),
                    "net_v_change": sum(row["high_label"] == "V" for row in values) - sum(row["low_label"] == "V" for row in values),
                }
                for obligation, values in sorted(exact_by_obligation.items())
            },
        },
        "interpretation_boundary": [
            "This decomposition was specified after the frozen T3 aggregate result and is descriptive/secondary.",
            "No obligation is promoted to a stable confirmatory finding from this file alone.",
            "The two reviewer channels remain separate; exact-agreed-resolved rows are an additional conservative view, not machine adjudication.",
        ],
        "inputs": {
            "generation_manifest_sha256": sha(P / "GENERATION_MANIFEST.json"),
            "private_map_sha256": sha(RUN / "human_review/PRIVATE_MAP.json"),
            **{f"{reviewer}_sha256": sha(HUMAN / f"{reviewer}.json") for reviewer in REVIEWERS},
        },
        "new_model_calls": 0,
        "new_human_labels": 0,
        "submitted_python_executed": False,
    }
    write(OUT / "CAPABILITY_ERROR_MIGRATION.json", result)

    lines = [
        "# RQ4 secondary: capability–error migration",
        "",
        "This is a post-hoc obligation-level mechanism decomposition of the frozen 128 GLM-4.7/GLM-5 pairs across 16 families. It adds no model calls or human labels and does not replace the preregistered program-level T3 result.",
        "",
        "## Separate reviewer channels",
        "",
    ]
    for reviewer in REVIEWERS:
        item = reviewer_results[reviewer]["overall"]
        lines.append(
            f"- {reviewer}: {item['obligation_pairs']} matched obligation pairs; "
            f"GLM-4.7 V={item['glm47_v']}, GLM-5 V={item['glm5_v']}, "
            f"RD={item['glm5_minus_glm47_v_risk_difference']:.4f}; "
            f"UNKNOWN worst-case interval={item['unknown_worst_case_risk_difference_interval']}."
        )
    lines += ["", "## Two-reviewer exact-resolved view", ""]
    exact = result["two_reviewer_exact_resolved"]
    lines.append(f"- Exact-resolved at both model outputs: {exact['all_labels_pairs']} obligation pairs; transitions={exact['all_labels_transition_counts']}.")
    lines.append(f"- Decidable C/V at both outputs: {exact['decidable_c_or_v_pairs']} pairs; transitions={exact['decidable_transition_counts']}.")
    shifts = sorted(
        ((name, item["net_v_change"], item["n"], item["transition_counts"]) for name, item in exact["by_obligation"].items()),
        key=lambda row: (abs(row[1]), row[0]),
        reverse=True,
    )
    lines += ["", "Largest exact-resolved net shifts by obligation (descriptive):", ""]
    for name, change, n, transitions in shifts[:8]:
        lines.append(f"- {name}: net V change {change:+d} over n={n}; {transitions}.")
    lines += [
        "",
        "## Claim boundary",
        "",
        "The frozen program-level capability contrast remains NOT ADMITTED. These obligation-level results may explain redistribution, persistence, or removal of error types, but are secondary and cannot be promoted to a new stable finding without a prospectively frozen replication.",
        "",
    ]
    (OUT / "CAPABILITY_ERROR_MIGRATION.md").write_text("\n".join(lines))
    print(json.dumps({
        "pairs": len(pairs),
        "reviewer_overall": {reviewer: reviewer_results[reviewer]["overall"] for reviewer in REVIEWERS},
        "exact": result["two_reviewer_exact_resolved"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
