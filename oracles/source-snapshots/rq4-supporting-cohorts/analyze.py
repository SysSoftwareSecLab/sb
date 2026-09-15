#!/usr/bin/env python3
"""Recompute the manuscript's narrow RQ4 supporting-cohort counts."""

from __future__ import annotations

from collections import Counter
import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "datasets/rq4-supporting-cohorts"


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def prospective(name: str, alias: str) -> dict:
    rows = read_csv(name)
    require(len(rows) == 120, f"{alias}: expected 120 rows")
    require({row["reviewer_alias"] for row in rows} == {alias}, f"{alias}: alias")
    require({row["category"] for row in rows} == {"F"}, f"{alias}: category")
    require({row["profile"] for row in rows} == {"glm47", "glm5"}, f"{alias}: profiles")
    require(len({row["task_id"] for row in rows}) == 60, f"{alias}: task count")
    require(
        all(Counter(row["profile"] for row in rows if row["task_id"] == task) == {"glm47": 1, "glm5": 1}
            for task in {row["task_id"] for row in rows}),
        f"{alias}: paired profile binding",
    )
    counts = {
        profile: dict(Counter(row["label"] for row in rows if row["profile"] == profile))
        for profile in ("glm47", "glm5")
    }
    return {"rows": len(rows), "paired_tasks": 60, "label_counts": counts}


def legacy() -> dict:
    rows = read_csv("legacy_final_truth.csv")
    require(len(rows) == 48, "legacy: expected 48 rows")
    require({row["channel"] for row in rows} == {"FinalTruth"}, "legacy: channel")
    require(len({row["triad"] for row in rows}) == 48, "legacy: triad binding")
    counts = {
        profile: dict(Counter(row[profile] for row in rows))
        for profile in ("glm47", "deepseek_flash", "glm5")
    }
    return {"rows": len(rows), "triads": 48, "label_counts": counts}


def analyze() -> dict:
    result = {
        "status": "PASS",
        "scope": (
            "Descriptive observation/branching counts. Reviewer channels share programs; "
            "cohorts are not pooled and are not direct physical-temporal endpoints."
        ),
        "prospective": {
            "Reviewer1": prospective("prospective_reviewer1.csv", "Reviewer1"),
            "Reviewer2": prospective("prospective_reviewer2.csv", "Reviewer2"),
        },
        "legacy_adjudication": legacy(),
    }
    expected = {
        "Reviewer1": {"glm47": 9, "glm5": 19},
        "Reviewer2": {"glm47": 8, "glm5": 18},
        "FinalTruth": {"glm47": 9, "glm5": 13},
    }
    for alias in ("Reviewer1", "Reviewer2"):
        actual = result["prospective"][alias]["label_counts"]
        for profile, value in expected[alias].items():
            require(actual[profile].get("V", 0) == value, f"{alias}/{profile}: V count")
    actual = result["legacy_adjudication"]["label_counts"]
    for profile, value in expected["FinalTruth"].items():
        require(actual[profile].get("V", 0) == value, f"FinalTruth/{profile}: V count")
    result["manuscript_counts"] = expected
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
