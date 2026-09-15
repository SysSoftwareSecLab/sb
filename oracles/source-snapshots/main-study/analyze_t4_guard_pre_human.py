"""Analyze the frozen T4 guard against original truth before post-guard review returns."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random


P = Path(__file__).resolve().parent
R = P.parents[3]
RUN = R / "05_formal/main_natural_384_v1"
HUMAN = RUN / "human_review/received_2026-09-12"
GUARD = RUN / "methods/guard"
OUT = RUN / "methods/analysis"
REVIEWERS = ("Reviewer1", "Reviewer2")
SUPPORTED_OBLIGATIONS = {
    "BUFFER_OCCUPANCY_OWNER",
    "BUFFER_RECEIPT",
    "BUFFER_EVENT_PROTOCOL",
    "DUAL_RESOURCE_SPAN",
    "REWORK_OBSERVATION",
    "REWORK_BRANCH",
}


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def quantile(values, probability):
    values = sorted(values)
    position = (len(values) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return values[low]
    return values[low] * (high - position) + values[high] * (position - low)


def family_cluster_interval(rows, field, replicates=20000, seed=20260912):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["family"]].append(1 if row[field] else 0)
    families = sorted(grouped)
    rng = random.Random(seed)
    samples = []
    for _ in range(replicates):
        picked = [rng.choice(families) for _ in families]
        values = [value for family in picked for value in grouped[family]]
        samples.append(sum(values) / len(values))
    return [quantile(samples, 0.025), quantile(samples, 0.975)]


def main():
    status = read(GUARD / "STATUS.json")
    assert status == {
        "status": "COMPLETE",
        "completed": 124,
        "total": 124,
        "natural": 108,
        "controlled": 16,
        "implementation_unchanged": True,
        "new_standalone_objects": 0,
    }
    scope = read(GUARD / "GUARD_HUMAN_REVIEW_SCOPE.json")
    assert scope["status"] == "LOCKED_BEFORE_GUARD_AGGREGATE_ANALYSIS"
    method_manifest = read(RUN / "methods/T4_METHOD_MANIFEST.json")
    objects = {item["object_id"]: item for item in method_manifest["objects"]}
    assert len(method_manifest["guard"]["natural_object_ids"]) == 108
    assert len(method_manifest["guard"]["controlled_object_ids"]) == 16

    reviews = {}
    for reviewer in REVIEWERS:
        validated = read(HUMAN / "validated" / (reviewer + ".json"))
        reviews[reviewer] = {row["review_id"]: row for row in validated["records"]}

    natural = []
    obligation_rows = []
    for object_id in method_manifest["guard"]["natural_object_ids"]:
        obj = objects[object_id]
        summary = read(GUARD / "results" / object_id / "SUMMARY.json")
        reasons = [row["obligation"] for row in summary["interventions"]]
        review_id = obj["review_id"]
        row = {
            "object_id": object_id,
            "review_id": review_id,
            "family": obj["family"],
            "axis": obj["axis"],
            "level": obj["level"],
            "layout": obj["layout"],
            "intervened": bool(reasons),
            "intervention_reasons": reasons,
            "reviewer_labels": {
                reviewer: reviews[reviewer][review_id]["program_label"]
                for reviewer in REVIEWERS
            },
        }
        natural.append(row)

        judgments = {
            reviewer: {
                item["obligation"]: item
                for item in reviews[reviewer][review_id]["judgments"]
            }
            for reviewer in REVIEWERS
        }
        for obligation in sorted(SUPPORTED_OBLIGATIONS):
            if not all(obligation in judgments[reviewer] for reviewer in REVIEWERS):
                continue
            pair = [judgments[reviewer][obligation] for reviewer in REVIEWERS]
            if not (
                pair[0]["scope_status"] == pair[1]["scope_status"] == "RESOLVED"
                and pair[0]["label"] == pair[1]["label"]
                and pair[0]["label"] in {"C", "V"}
            ):
                continue
            if obligation in reasons:
                observation = "MATCHING_TRIGGER"
            elif not reasons:
                observation = "NO_TRIGGER_FULL_ORIGINAL_PATH_OBSERVED"
            else:
                observation = "CENSORED_BY_OTHER_TRIGGER"
            obligation_rows.append({
                "object_id": object_id,
                "family": obj["family"],
                "obligation": obligation,
                "truth": pair[0]["label"],
                "observation": observation,
            })

    assert len(natural) == 108
    assert sum(row["intervened"] for row in natural) == 53
    assert sum(len(row["intervention_reasons"]) for row in natural) == 54

    reviewer_specific = {}
    for reviewer in REVIEWERS:
        counts = Counter(
            (row["reviewer_labels"][reviewer], "BLOCK" if row["intervened"] else "ALLOW")
            for row in natural
        )
        unsafe = sum(counts[("UNSAFE", decision)] for decision in ("BLOCK", "ALLOW"))
        safe = sum(counts[("SAFE", decision)] for decision in ("BLOCK", "ALLOW"))
        reviewer_specific[reviewer] = {
            "confusion": {label + "->" + decision: count for (label, decision), count in sorted(counts.items())},
            "unsafe_programs": unsafe,
            "block_rate_on_unsafe": counts[("UNSAFE", "BLOCK")] / unsafe if unsafe else None,
            "allow_rate_on_unsafe": counts[("UNSAFE", "ALLOW")] / unsafe if unsafe else None,
            "safe_programs": safe,
            "block_rate_on_safe": counts[("SAFE", "BLOCK")] / safe if safe else None,
        }

    exact = [
        row
        for row in natural
        if row["reviewer_labels"][REVIEWERS[0]] == row["reviewer_labels"][REVIEWERS[1]]
    ]
    exact_counts = Counter(
        (row["reviewer_labels"][REVIEWERS[0]], "BLOCK" if row["intervened"] else "ALLOW")
        for row in exact
    )
    exact_unsafe = [row for row in exact if row["reviewer_labels"][REVIEWERS[0]] == "UNSAFE"]
    exact_miss_rate = sum(not row["intervened"] for row in exact_unsafe) / len(exact_unsafe)
    miss_families = sorted({row["family"] for row in exact_unsafe if not row["intervened"]})
    all_unsafe_families = sorted({row["family"] for row in exact_unsafe})
    by_family = {}
    for family in all_unsafe_families:
        rows = [row for row in exact_unsafe if row["family"] == family]
        by_family[family] = {
            "agreed_unsafe": len(rows),
            "blocked": sum(row["intervened"] for row in rows),
            "allowed": sum(not row["intervened"] for row in rows),
        }

    by_obligation = {}
    for obligation in sorted(SUPPORTED_OBLIGATIONS):
        rows = [row for row in obligation_rows if row["obligation"] == obligation]
        counts = Counter((row["truth"], row["observation"]) for row in rows)
        by_obligation[obligation] = {
            "exact_agreed_resolved": len(rows),
            "counts": {
                truth + "->" + observation: count
                for (truth, observation), count in sorted(counts.items())
            },
        }

    controlled = []
    qualification = read(P / "MUTATION_HOLDOUT_QUALIFICATION.json")
    assert qualification["status"] == "PASS" and qualification["cases"] == 8
    for object_id in method_manifest["guard"]["controlled_object_ids"]:
        obj = objects[object_id]
        summary = read(GUARD / "results" / object_id / "SUMMARY.json")
        controlled.append({
            "object_id": object_id,
            "role": obj["controlled_role"],
            "family": obj["family"],
            "level": obj["level"],
            "layout": obj["layout"],
            "interventions": summary["intervention_count"],
            "terminal_label": summary["task_labels"]["TERMINAL"],
        })
    assert all(row["interventions"] == 0 for row in controlled)

    result = {
        "status": "T4_GUARD_PRE_POST_HUMAN_ANALYSIS_COMPLETE",
        "scope": (
            "Detection coverage on the already reviewed original natural paths plus the frozen "
            "MF-H1 controlled table. This is not a post-guard safety/effect estimate."
        ),
        "implementation_unchanged": True,
        "natural": {
            "objects": len(natural),
            "blocked": sum(row["intervened"] for row in natural),
            "allowed": sum(not row["intervened"] for row in natural),
            "interventions": sum(len(row["intervention_reasons"]) for row in natural),
            "intervention_reason_counts": dict(Counter(reason for row in natural for reason in row["intervention_reasons"])),
            "reviewer_specific": reviewer_specific,
            "exact_program_agreement": {
                "programs": len(exact),
                "confusion": {label + "->" + decision: count for (label, decision), count in sorted(exact_counts.items())},
                "agreed_unsafe": len(exact_unsafe),
                "blocked_agreed_unsafe": sum(row["intervened"] for row in exact_unsafe),
                "allowed_agreed_unsafe": sum(not row["intervened"] for row in exact_unsafe),
                "allow_rate_on_agreed_unsafe": exact_miss_rate,
                "family_cluster_bootstrap_95": family_cluster_interval(
                    [{**row, "missed": not row["intervened"]} for row in exact_unsafe], "missed"
                ),
                "unsafe_families": len(all_unsafe_families),
                "families_with_at_least_one_allowed_unsafe": len(miss_families),
                "family_failure_fraction": len(miss_families) / len(all_unsafe_families),
                "by_family": by_family,
                "admission_note": (
                    "Descriptive program-level coverage result only. It does not satisfy the frozen "
                    "method-by-obligation stable-finding gate and is not a guard risk-difference claim."
                ),
            },
            "supported_obligations_exact_agreed_resolved": by_obligation,
        },
        "controlled_mf_h1": {
            "scope": "Separate controlled table; never pooled into natural defect rates.",
            "mutation_family": qualification["family"],
            "mutations": sum(row["role"] == "MUTATION" for row in controlled),
            "mutations_terminal_v": sum(row["role"] == "MUTATION" and row["terminal_label"] == "V" for row in controlled),
            "mutations_blocked": sum(row["role"] == "MUTATION" and row["interventions"] > 0 for row in controlled),
            "matched_references": sum(row["role"] == "MATCHED_REFERENCE" for row in controlled),
            "matched_references_terminal_c": sum(row["role"] == "MATCHED_REFERENCE" and row["terminal_label"] == "C" for row in controlled),
            "matched_references_blocked": sum(row["role"] == "MATCHED_REFERENCE" and row["interventions"] > 0 for row in controlled),
            "interpretation": (
                "The unchanged scope-limited guard did not cover the secondary-resource cleanup "
                "omission: all eight qualified mutations passed without intervention, as did all "
                "eight matched correct references."
            ),
        },
        "post_guard_human": {
            "changed_trajectories": 53,
            "semantically_identical_reused": 55,
            "status": "WAITING_FOR_SINGLE_DOUBLE_REVIEW_RETURN",
            "effect_claim_allowed_now": False,
        },
        "new_model_calls": 0,
        "new_candidate_executions": 0,
        "new_human_labels": 0,
    }
    write(OUT / "GUARD_PRE_POST_HUMAN.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
