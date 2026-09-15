"""Analyze the completed frozen T4 source-only judge collection."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random


P = Path(__file__).resolve().parent
R = P.parents[3]
RUN = R / "05_formal/main_natural_384_v1"
METHODS = RUN / "methods"
HUMAN = RUN / "human_review/received_2026-09-12"
OUT = METHODS / "analysis"
REVIEWERS = ("Reviewer1", "Reviewer2")
JUDGES = ("deepseek_flash", "glm5")
SLICE_FIELDS = ("obligation", "family", "axis", "level", "layout", "generation_model", "prompt")


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


def cluster_interval(rows, predicate, seed, replicates=20000):
    by_family = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(1 if predicate(row) else 0)
    families = sorted(by_family)
    if not families:
        return [None, None]
    rng = random.Random(seed)
    samples = []
    for _ in range(replicates):
        selected = [rng.choice(families) for _ in families]
        values = [value for family in selected for value in by_family[family]]
        samples.append(sum(values) / len(values))
    return [quantile(samples, 0.025), quantile(samples, 0.975)]


def performance(rows):
    confusion = Counter((row["truth"], row["prediction"]) for row in rows)
    true_v = [row for row in rows if row["truth"] == "V"]
    true_c = [row for row in rows if row["truth"] == "C"]
    finite = [row for row in rows if row["prediction"] in {"C", "V"}]
    return {
        "n": len(rows),
        "truth_counts": dict(Counter(row["truth"] for row in rows)),
        "prediction_counts": dict(Counter(row["prediction"] for row in rows)),
        "confusion": {
            truth + "->" + prediction: count
            for (truth, prediction), count in sorted(confusion.items())
        },
        "finite_coverage": len(finite) / len(rows) if rows else None,
        "true_v": len(true_v),
        "v_recall": sum(row["prediction"] == "V" for row in true_v) / len(true_v) if true_v else None,
        "wrong_c_on_v": sum(row["prediction"] == "C" for row in true_v) / len(true_v) if true_v else None,
        "u_or_na_on_v": sum(row["prediction"] in {"U", "NA"} for row in true_v) / len(true_v) if true_v else None,
        "invalid_on_v": sum(row["prediction"] == "INVALID" for row in true_v) / len(true_v) if true_v else None,
        "inapplicable_on_v": sum(row["prediction"] == "METHOD_INAPPLICABLE" for row in true_v) / len(true_v) if true_v else None,
        "non_detection_on_v": sum(row["prediction"] != "V" for row in true_v) / len(true_v) if true_v else None,
        "true_c": len(true_c),
        "v_on_c": sum(row["prediction"] == "V" for row in true_c) / len(true_c) if true_c else None,
    }


def slices(rows):
    output = {}
    for field in SLICE_FIELDS:
        output[field] = {}
        for value in sorted({str(row[field]) for row in rows}):
            selected = [row for row in rows if str(row[field]) == value]
            output[field][value] = performance(selected)
    return output


def stable_gate(judge, obligation, rows):
    true_v = [row for row in rows if row["truth"] == "V"]
    families = sorted({row["family"] for row in true_v})
    output = {
        "judge": judge,
        "obligation": obligation,
        "resolved_v": len(true_v),
        "families": len(families),
    }
    predicates = {
        "non_detection": lambda row: row["prediction"] != "V",
        "wrong_c": lambda row: row["prediction"] == "C",
    }
    admitted_types = []
    for offset, (name, predicate) in enumerate(predicates.items()):
        failures = [row for row in true_v if predicate(row)]
        failed_families = {row["family"] for row in failures}
        rate = len(failures) / len(true_v) if true_v else None
        family_fraction = len(failed_families) / len(families) if families else None
        interval = cluster_interval(
            true_v,
            predicate,
            20260912 + offset + sum(ord(ch) for ch in judge + obligation),
        )
        admitted = (
            len(true_v) >= 20
            and len(families) >= 4
            and rate is not None
            and rate >= 0.25
            and family_fraction is not None
            and family_fraction >= 0.5
            and interval[0] is not None
            and interval[0] > 0.10
        )
        output[name] = {
            "count": len(failures),
            "rate": rate,
            "families_with_failure": len(failed_families),
            "family_failure_fraction": family_fraction,
            "family_cluster_bootstrap_95": interval,
            "admitted": admitted,
        }
        if admitted:
            admitted_types.append(name)
    output["admitted"] = bool(admitted_types)
    output["admitted_failure_types"] = admitted_types
    return output


def program_decision(result, obligations):
    if result is None:
        return "METHOD_INAPPLICABLE"
    if result["status"] != "VALID_STRUCTURED_PREDICTIONS":
        return "INVALID"
    labels = {row["id"]: row["label"] for row in result["predictions"]}
    assert set(labels) == set(obligations)
    if "V" in labels.values():
        return "UNSAFE"
    if "U" in labels.values():
        return "UNKNOWN"
    return "SAFE"


def program_comparison(rows, truth_key):
    counts = Counter((row[truth_key], row["decision"]) for row in rows)
    unsafe = [row for row in rows if row[truth_key] == "UNSAFE"]
    safe = [row for row in rows if row[truth_key] == "SAFE"]
    return {
        "programs": len(rows),
        "confusion": {
            truth + "->" + prediction: count
            for (truth, prediction), count in sorted(counts.items())
        },
        "unsafe_programs": len(unsafe),
        "detected_unsafe": sum(row["decision"] == "UNSAFE" for row in unsafe),
        "residual_unsafe": sum(row["decision"] != "UNSAFE" for row in unsafe),
        "residual_unsafe_rate": sum(row["decision"] != "UNSAFE" for row in unsafe) / len(unsafe) if unsafe else None,
        "wrong_safe_on_unsafe": sum(row["decision"] == "SAFE" for row in unsafe),
        "safe_programs": len(safe),
        "unsafe_on_safe": sum(row["decision"] == "UNSAFE" for row in safe),
        "unsafe_on_safe_rate": sum(row["decision"] == "UNSAFE" for row in safe) / len(safe) if safe else None,
    }


def main():
    collection = read(METHODS / "source_judge/STATUS.json")
    assert collection == {
        "status": "COMPLETE",
        "completed": 798,
        "total": 798,
        "valid": 707,
        "invalid": 91,
        "scientific_retries": 0,
        "new_standalone_objects": 0,
    }
    manifest = read(METHODS / "T4_METHOD_MANIFEST.json")
    generation = {row["slot_id"]: row for row in read(P / "GENERATION_MANIFEST.json")}
    objects = {row["object_id"]: row for row in manifest["objects"]}
    natural_objects = [row for row in manifest["objects"] if row["kind"] == "NATURAL"]
    controlled_objects = [row for row in manifest["objects"] if row["kind"] == "CONTROLLED"]
    assert len(natural_objects) == 384 and len(controlled_objects) == 16

    results = {}
    for slot in manifest["source_judge"]["slots"]:
        result = read(METHODS / "source_judge/results" / slot["judge_slot_id"] / "RESULT.json")
        assert result["object_id"] == slot["object_id"] and result["judge"] == slot["judge"]
        assert result["model_identity_matches"] is True
        results[(slot["judge"], slot["object_id"])] = result
    assert len(results) == 798

    reviews = {}
    for reviewer in REVIEWERS:
        validated = read(HUMAN / "validated" / (reviewer + ".json"))
        reviews[reviewer] = {row["review_id"]: row for row in validated["records"]}

    output = {
        "status": "T4_SOURCE_JUDGE_ANALYSIS_COMPLETE",
        "collection": collection,
        "truth_policy": "Two independent reviewer channels; primary exact table only uses same-label, both-resolved C/V judgments.",
        "natural_program_denominator": 384,
        "controlled_separate": True,
        "judges": {},
        "admitted_stable_blind_spots": [],
    }
    for judge in JUDGES:
        exact_rows = []
        reviewer_rows = {reviewer: [] for reviewer in REVIEWERS}
        program_rows = []
        for obj in natural_objects:
            slot = generation[obj["slot_id"]]
            result = results.get((judge, obj["object_id"]))
            if result is None:
                assert not obj["judge_eligible"]
                predictions = {obligation: "METHOD_INAPPLICABLE" for obligation in obj["obligations"]}
            elif result["status"] == "VALID_STRUCTURED_PREDICTIONS":
                predictions = {row["id"]: row["label"] for row in result["predictions"]}
                assert set(predictions) == set(obj["obligations"])
            else:
                predictions = {obligation: "INVALID" for obligation in obj["obligations"]}

            review_id = obj["review_id"]
            judgments = {
                reviewer: {row["obligation"]: row for row in reviews[reviewer][review_id]["judgments"]}
                for reviewer in REVIEWERS
            }
            for obligation in obj["obligations"]:
                base = {
                    "object_id": obj["object_id"],
                    "review_id": review_id,
                    "obligation": obligation,
                    "prediction": predictions[obligation],
                    "family": obj["family"],
                    "axis": obj["axis"],
                    "level": obj["level"],
                    "layout": obj["layout"],
                    "generation_model": slot["profile"],
                    "prompt": slot["prompt"],
                }
                pair = [judgments[reviewer][obligation] for reviewer in REVIEWERS]
                for reviewer, truth in zip(REVIEWERS, pair):
                    reviewer_rows[reviewer].append({
                        **base,
                        "truth": truth["label"],
                        "scope_status": truth["scope_status"],
                    })
                if (
                    pair[0]["scope_status"] == pair[1]["scope_status"] == "RESOLVED"
                    and pair[0]["label"] == pair[1]["label"]
                    and pair[0]["label"] in {"C", "V"}
                ):
                    exact_rows.append({**base, "truth": pair[0]["label"]})

            labels = {reviewer: reviews[reviewer][review_id]["program_label"] for reviewer in REVIEWERS}
            program_rows.append({
                "object_id": obj["object_id"],
                "family": obj["family"],
                "decision": program_decision(result, obj["obligations"]),
                **{"truth_" + reviewer: labels[reviewer] for reviewer in REVIEWERS},
                "truth_exact": labels[REVIEWERS[0]] if labels[REVIEWERS[0]] == labels[REVIEWERS[1]] else "DISAGREEMENT",
            })

        stable = []
        for obligation in sorted({row["obligation"] for row in exact_rows}):
            pattern = stable_gate(judge, obligation, [row for row in exact_rows if row["obligation"] == obligation])
            stable.append(pattern)
            if pattern["admitted"]:
                output["admitted_stable_blind_spots"].append(pattern)
        reviewer_specific = {}
        for reviewer, rows in reviewer_rows.items():
            resolved_cv = [row for row in rows if row["scope_status"] == "RESOLVED" and row["truth"] in {"C", "V"}]
            reviewer_specific[reviewer] = {
                "all_truth_label_counts": dict(Counter(row["truth"] for row in rows)),
                "resolved_cv": performance(resolved_cv),
                "resolved_cv_slices": slices(resolved_cv),
                "program_level": program_comparison(program_rows, "truth_" + reviewer),
            }

        exact_programs = [row for row in program_rows if row["truth_exact"] != "DISAGREEMENT"]
        output["judges"][judge] = {
            "attempted_natural": sum((judge, obj["object_id"]) in results for obj in natural_objects),
            "method_inapplicable_natural": sum((judge, obj["object_id"]) not in results for obj in natural_objects),
            "valid_natural_responses": sum(results[(judge, obj["object_id"])]["status"] == "VALID_STRUCTURED_PREDICTIONS" for obj in natural_objects if (judge, obj["object_id"]) in results),
            "invalid_natural_responses": sum(results[(judge, obj["object_id"])]["status"] != "VALID_STRUCTURED_PREDICTIONS" for obj in natural_objects if (judge, obj["object_id"]) in results),
            "primary_exact_agreed_resolved": performance(exact_rows),
            "primary_slices": slices(exact_rows),
            "stable_blind_spot_gate": stable,
            "admitted_stable_blind_spots": [row for row in stable if row["admitted"]],
            "reviewer_specific": reviewer_specific,
            "program_level_exact_agreement": program_comparison(exact_programs, "truth_exact"),
        }

    qualification = read(P / "MUTATION_HOLDOUT_QUALIFICATION.json")
    assert qualification["status"] == "PASS" and qualification["cases"] == 8
    controlled = {}
    for judge in JUDGES:
        rows = []
        for obj in controlled_objects:
            result = results[(judge, obj["object_id"])]
            if result["status"] == "VALID_STRUCTURED_PREDICTIONS":
                assert len(result["predictions"]) == 1 and result["predictions"][0]["id"] == "TASK_GOAL"
                prediction = result["predictions"][0]["label"]
            else:
                prediction = "INVALID"
            truth = "V" if obj["controlled_role"] == "MUTATION" else "C"
            rows.append({
                "object_id": obj["object_id"],
                "case_id": obj["mutation_case_id"],
                "role": obj["controlled_role"],
                "family": obj["family"],
                "level": obj["level"],
                "layout": obj["layout"],
                "truth": truth,
                "prediction": prediction,
            })
        controlled[judge] = {
            "summary": performance(rows),
            "paired_cases": rows,
        }
    output["controlled_mf_h1"] = {
        "scope": "Eight qualified secondary-resource-release-omission mutations and eight matched correct references; never pooled into natural rates.",
        "mutation_family": qualification["family"],
        "judges": controlled,
    }
    output["new_model_calls_beyond_frozen_manifest"] = 0
    output["scientific_retries"] = 0
    output["new_human_labels"] = 0
    write(OUT / "SOURCE_JUDGE.json", output)
    print(json.dumps({
        "status": output["status"],
        "collection": collection,
        "judge_primary": {
            judge: {
                "valid_natural": output["judges"][judge]["valid_natural_responses"],
                "invalid_natural": output["judges"][judge]["invalid_natural_responses"],
                "exact": output["judges"][judge]["primary_exact_agreed_resolved"],
                "stable": output["judges"][judge]["admitted_stable_blind_spots"],
                "program_exact": output["judges"][judge]["program_level_exact_agreement"],
            }
            for judge in JUDGES
        },
        "controlled": {
            judge: controlled[judge]["summary"] for judge in JUDGES
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
