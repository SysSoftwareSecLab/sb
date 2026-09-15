"""Analyze already-existing prompt and dynamic-checker T4 evidence."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random


P = Path(__file__).resolve().parent
R = P.parents[3]
RUN = R / "05_formal/main_natural_384_v1"
HUMAN = RUN / "human_review/received_2026-09-12"
OUT = RUN / "methods/analysis"
REVIEWERS = ("Reviewer1", "Reviewer2")


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def quantile(values, p):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * p
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return values[low]
    return values[low] * (high - position) + values[high] * (position - low)


def truth_summary(rows):
    confusion = Counter((x["truth"], x["prediction"]) for x in rows)
    true_v = [x for x in rows if x["truth"] == "V"]
    true_c = [x for x in rows if x["truth"] == "C"]
    finite = [x for x in rows if x["prediction"] in {"C", "V"}]
    return {
        "n": len(rows),
        "truth_counts": dict(Counter(x["truth"] for x in rows)),
        "prediction_counts": dict(Counter(x["prediction"] for x in rows)),
        "confusion": {a + "->" + b: n for (a, b), n in sorted(confusion.items())},
        "finite_coverage": len(finite) / len(rows) if rows else None,
        "true_v": len(true_v),
        "v_recall": sum(x["prediction"] == "V" for x in true_v) / len(true_v) if true_v else None,
        "wrong_c_on_v": sum(x["prediction"] == "C" for x in true_v) / len(true_v) if true_v else None,
        "non_detection_on_v": sum(x["prediction"] != "V" for x in true_v) / len(true_v) if true_v else None,
        "true_c": len(true_c),
        "v_on_c": sum(x["prediction"] == "V" for x in true_c) / len(true_c) if true_c else None,
    }


def stable_blind_spot(obligation, rows, replicates=20000, seed=20260912):
    true_v = [x for x in rows if x["truth"] == "V"]
    by_family = defaultdict(list)
    for row in true_v:
        by_family[row["family"]].append(1 if row["prediction"] != "V" else 0)
    families = sorted(by_family)
    rate = sum(sum(x) for x in by_family.values()) / len(true_v) if true_v else None
    family_occurrence = sum(any(x) for x in by_family.values()) / len(families) if families else None
    interval = [None, None]
    if families:
        rng = random.Random(seed + sum(ord(x) for x in obligation))
        samples = []
        for _ in range(replicates):
            picked = [rng.choice(families) for _ in families]
            values = [v for family in picked for v in by_family[family]]
            samples.append(sum(values) / len(values))
        interval = [quantile(samples, 0.025), quantile(samples, 0.975)]
    admitted = (
        len(true_v) >= 20 and len(families) >= 4 and rate is not None and rate >= 0.25
        and family_occurrence is not None and family_occurrence >= 0.5
        and interval[0] is not None and interval[0] > 0.10
    )
    return {
        "obligation": obligation,
        "resolved_v": len(true_v),
        "families": len(families),
        "non_detection_rate": rate,
        "families_with_failure_fraction": family_occurrence,
        "family_cluster_bootstrap_95": interval,
        "admitted": admitted,
    }


def dynamic_predictions(slot_id):
    folder = RUN / "evidence" / slot_id
    result = {}
    task_path = folder / "TASK_EVIDENCE.json"
    if task_path.exists():
        for row in read(task_path).get("rows", []):
            name = "TASK_GOAL" if row.get("obligation") == "TERMINAL" else row.get("obligation")
            if name:
                result[name] = row.get("label", "MISSING")
    grammar_path = folder / "GRAMMAR_EVIDENCE.json"
    if grammar_path.exists():
        for row in read(grammar_path).get("rows", []):
            if row.get("obligation"):
                result[row["obligation"]] = row.get("label", "MISSING")
    return result


def main():
    method_manifest = read(RUN / "methods/T4_METHOD_MANIFEST.json")
    assert method_manifest["status"] == "T4_METHOD_INPUTS_FROZEN_ZERO_CALLS_ZERO_EXECUTIONS"
    generation = {x["slot_id"]: x for x in read(P / "GENERATION_MANIFEST.json")}
    private = read(RUN / "human_review/PRIVATE_MAP.json")
    slot_by_review = {rid: value["slot_id"] for rid, value in private.items()}
    reviews = {name: read(HUMAN / "validated" / (name + ".json")) for name in REVIEWERS}
    human = {
        name: {
            rec["review_id"]: {
                "program_label": rec["program_label"],
                "judgments": {x["obligation"]: x for x in rec["judgments"]},
            }
            for rec in reviews[name]["records"]
        }
        for name in REVIEWERS
    }

    dynamic_rows = {name: [] for name in REVIEWERS}
    exact_rows = []
    for rid, slot_id in slot_by_review.items():
        slot = generation[slot_id]
        predictions = dynamic_predictions(slot_id)
        for obligation in set(human[REVIEWERS[0]][rid]["judgments"]) | set(human[REVIEWERS[1]][rid]["judgments"]):
            prediction = predictions.get(obligation, "METHOD_INAPPLICABLE")
            base = {
                "review_id": rid, "slot_id": slot_id, "family": slot["family"],
                "axis": slot["axis"], "level": slot["level"], "obligation": obligation,
                "prediction": prediction,
            }
            judgments = [human[name][rid]["judgments"][obligation] for name in REVIEWERS]
            for name, judgment in zip(REVIEWERS, judgments):
                dynamic_rows[name].append({**base, "truth": judgment["label"], "scope_status": judgment["scope_status"]})
            if judgments[0]["scope_status"] == judgments[1]["scope_status"] == "RESOLVED" and judgments[0]["label"] == judgments[1]["label"]:
                exact_rows.append({**base, "truth": judgments[0]["label"]})

    exact_finite = [x for x in exact_rows if x["truth"] in {"C", "V"}]
    by_obligation = {}
    stable = []
    for obligation in sorted({x["obligation"] for x in exact_finite}):
        rows = [x for x in exact_finite if x["obligation"] == obligation]
        by_obligation[obligation] = truth_summary(rows)
        stable.append(stable_blind_spot(obligation, rows))
    dynamic = {
        "scope": "Existing stored checker output only; no natural candidate rerun and no human disagreement adjudication.",
        "reviewer_specific": {
            name: truth_summary([x for x in rows if x["truth"] in {"C", "V"}])
            for name, rows in dynamic_rows.items()
        },
        "exact_agreed_resolved": truth_summary(exact_finite),
        "by_obligation_exact_agreed_resolved": by_obligation,
        "stable_blind_spot_gate": stable,
        "admitted_stable_blind_spots": [x for x in stable if x["admitted"]],
        "method_inapplicable_exact": sum(x["prediction"] == "METHOD_INAPPLICABLE" for x in exact_rows),
    }

    # Existing safety-reminder versus base pairs, now decomposed by obligation.
    prompt = {name: {} for name in REVIEWERS}
    groups = defaultdict(dict)
    for rid, slot_id in slot_by_review.items():
        slot = generation[slot_id]
        key = (slot["task_id"], slot["profile"], slot["repeat"])
        groups[key][slot["prompt"]] = rid
    assert len(groups) == 192 and all(set(x) == {"base", "safety_reminder"} for x in groups.values())
    for reviewer in REVIEWERS:
        rows_by_obligation = defaultdict(list)
        for key, pair in groups.items():
            low, high = pair["base"], pair["safety_reminder"]
            low_j = human[reviewer][low]["judgments"]
            high_j = human[reviewer][high]["judgments"]
            assert set(low_j) == set(high_j)
            for obligation in low_j:
                rows_by_obligation[obligation].append({"base": low_j[obligation]["label"], "safety_reminder": high_j[obligation]["label"]})
        for obligation, rows in sorted(rows_by_obligation.items()):
            n = len(rows)
            prompt[reviewer][obligation] = {
                "pairs": n,
                "base_counts": dict(Counter(x["base"] for x in rows)),
                "safety_reminder_counts": dict(Counter(x["safety_reminder"] for x in rows)),
                "v_rate_difference_full_denominator": (
                    sum(x["safety_reminder"] == "V" for x in rows) - sum(x["base"] == "V" for x in rows)
                ) / n,
                "unknown_or_na_pair_count": sum("U" in (x["base"], x["safety_reminder"]) or "NA" in (x["base"], x["safety_reminder"]) for x in rows),
            }

    result = {
        "status": "T4_EXISTING_PROMPT_AND_DYNAMIC_ANALYSIS_COMPLETE",
        "dynamic": dynamic,
        "prompt_obligation_pairs": prompt,
        "prompt_program_level": read(RUN / "analysis/MAIN_TABLES.json")["paired"]["PROMPT_SECONDARY"],
        "new_model_calls": 0,
        "new_candidate_executions": 0,
        "new_human_labels": 0,
    }
    write(OUT / "PROMPT_DYNAMIC.json", result)
    print(json.dumps({
        "status": result["status"],
        "dynamic_exact": dynamic["exact_agreed_resolved"],
        "dynamic_inapplicable_exact": dynamic["method_inapplicable_exact"],
        "stable_blind_spots": dynamic["admitted_stable_blind_spots"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
