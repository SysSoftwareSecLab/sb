"""Describe human-review agreement before joining model/task assignments."""
from collections import Counter, defaultdict
import json
from pathlib import Path


P = Path(__file__).resolve().parent
R = P.parents[3]
ROOT = R / "05_formal/main_natural_384_v1/human_review/received_2026-09-12"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def as_rows(counter, left="Reviewer1", right="Reviewer2"):
    return [
        {left: a, right: b, "n": n}
        for (a, b), n in sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    ]


def main():
    a_data = read(ROOT / "validated/Reviewer1.json")
    b_data = read(ROOT / "validated/Reviewer2.json")
    a = {x["review_id"]: x for x in a_data["records"]}
    b = {x["review_id"]: x for x in b_data["records"]}
    program = Counter()
    label = Counter()
    scope = Counter()
    per_obligation = defaultdict(lambda: {"labels": Counter(), "scopes": Counter(), "programs": set()})
    disagreement_burden = Counter()
    for rid in sorted(a):
        ra, rb = a[rid], b[rid]
        program[(ra["program_label"], rb["program_label"])] += 1
        ja = {x["obligation"]: x for x in ra["judgments"]}
        jb = {x["obligation"]: x for x in rb["judgments"]}
        for obligation in ja:
            x, y = ja[obligation], jb[obligation]
            label[(x["label"], y["label"])] += 1
            scope[(x["scope_status"], y["scope_status"])] += 1
            item = per_obligation[obligation]
            item["labels"][(x["label"], y["label"])] += 1
            item["scopes"][(x["scope_status"], y["scope_status"])] += 1
            item["programs"].add(rid)
            if x["label"] != y["label"] or x["scope_status"] != y["scope_status"]:
                disagreement_burden[rid] += 1
    result = {
        "status": "BLINDED_REVIEW_ID_ONLY_NO_MODEL_OR_EXPERIMENTAL_ASSIGNMENT_JOIN",
        "program_label_confusion": as_rows(program),
        "judgment_label_confusion": as_rows(label),
        "scope_confusion": as_rows(scope, "Reviewer1_scope", "Reviewer2_scope"),
        "by_obligation": {
            key: {
                "programs": len(value["programs"]),
                "label_confusion": as_rows(value["labels"]),
                "scope_confusion": as_rows(value["scopes"], "Reviewer1_scope", "Reviewer2_scope"),
                "disagreements": sum(
                    n for (x, y), n in value["labels"].items() if x != y
                ) + sum(
                    n for (x, y), n in value["scopes"].items() if x != y
                ),
            }
            for key, value in sorted(per_obligation.items())
        },
        "program_disagreement_burden": {
            "programs_with_zero_judgment_disagreements": 384 - len(disagreement_burden),
            "programs_with_one_or_more_judgment_disagreements": len(disagreement_burden),
            "histogram": dict(sorted(Counter(disagreement_burden.values()).items())),
            "maximum": max(disagreement_burden.values(), default=0),
        },
    }
    write(ROOT / "BLIND_AGREEMENT.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
