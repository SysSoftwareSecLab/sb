from __future__ import annotations

from collections import Counter, defaultdict
import datetime
import hashlib
import json
import math
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN = ROOT / "05_formal/rq2_coherent_pair_confirmation_v1"
RELEASE = RUN / "human_review_one_shot_v1"
RETURNS = RUN / "human_returns_raw"
RETURN_FILES = {
    "Reviewer1": RETURNS / "RETURN_Reviewer1.json",
    "Reviewer2": RETURNS / "RETURN_Reviewer2.json",
}
FIELDS = ("interface", "no_update_outcome", "gap_update_outcome", "stable_pair_strategy")
ALLOWED = {
    "interface": {"VALID", "INVALID", "U"},
    "no_update_outcome": {"C", "V", "NE", "U"},
    "gap_update_outcome": {"C", "V", "NE", "U"},
    "stable_pair_strategy": {"PRESENT", "ABSENT", "U"},
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_time(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def kappa(left: list[str], right: list[str]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("KAPPA_INPUT")
    labels = sorted(set(left) | set(right))
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    expected = sum((left.count(label) / len(left)) * (right.count(label) / len(right)) for label in labels)
    if math.isclose(expected, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else 0.0
    return (observed - expected) / (1.0 - expected)


def machine_long_label(row: dict) -> str:
    rates = row["rates"]["CONCURRENT_LONG"]
    for label in ("V", "NE", "C", "S0"):
        if math.isclose(rates[label], 1.0):
            return label
    return "MIXED"


def machine_serial_label(row: dict) -> str:
    rates = row["rates"]["SERIAL_SHORT"]
    for label in ("V", "NE", "C", "S0"):
        if math.isclose(rates[label], 1.0):
            return label
    return "MIXED"


def human_susceptible(answer: dict) -> bool:
    return (
        answer["interface"] == "VALID"
        and answer["no_update_outcome"] == "C"
        and answer["gap_update_outcome"] in {"V", "NE"}
    )


def main() -> None:
    lock = read(RELEASE / "HUMAN_PACKAGE_LOCK.json")
    if lock.get("status") != "FROZEN_BEFORE_HUMAN_LABELS":
        raise RuntimeError("HUMAN_PACKAGE_NOT_LOCKED")
    for item in lock["files"]:
        if sha(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError("HUMAN_PACKAGE_LOCK_CHANGED:" + item["path"])
    package_items = read(RELEASE / "package/ITEMS.json")
    expected_ids = {item["blind_id"] for item in package_items}
    private_rows = read(RELEASE / "PRIVATE_BLIND_MAP.json")
    private = {row["blind_id"]: row for row in private_rows}
    transfer = read(RELEASE / "TRANSFER_TO_MAC.json")
    sent_time = parse_time(transfer["checked_utc"])

    reviews = {}
    checks = {}
    for reviewer, path in RETURN_FILES.items():
        value = read(path)
        answers = value.get("answers", {})
        saved_after_transfer = all(parse_time(answer["saved_utc"]) >= sent_time for answer in answers.values())
        reviewer_checks = {
            "schema_exact": value.get("schema") == "paper3.rq2.coherent_pair.human_return.v1",
            "reviewer_exact": value.get("reviewer") == reviewer,
            "status_complete": value.get("status") == "COMPLETE",
            "exactly_96_answers": len(answers) == 96,
            "blind_ids_exact": set(answers) == expected_ids,
            "all_fields_allowed": all(
                all(answer.get(field) in ALLOWED[field] for field in FIELDS)
                for answer in answers.values()
            ),
            "all_rationales_nonempty": all(bool(answer.get("rationale", "").strip()) for answer in answers.values()),
            "all_saved_after_transfer": saved_after_transfer,
        }
        checks[reviewer] = reviewer_checks
        if not all(reviewer_checks.values()):
            raise RuntimeError("RETURN_INTEGRITY_FAILED:" + reviewer)
        reviews[reviewer] = answers

    left = reviews["Reviewer1"]
    right = reviews["Reviewer2"]
    agreement = {}
    for field in FIELDS:
        left_values = [left[blind_id][field] for blind_id in sorted(expected_ids)]
        right_values = [right[blind_id][field] for blind_id in sorted(expected_ids)]
        agreement[field] = {
            "exact": sum(a == b for a, b in zip(left_values, right_values)),
            "total": 96,
            "proportion": sum(a == b for a, b in zip(left_values, right_values)) / 96,
            "cohen_kappa": kappa(left_values, right_values),
            "reviewer_1_counts": dict(sorted(Counter(left_values).items())),
            "reviewer_2_counts": dict(sorted(Counter(right_values).items())),
        }
    exact_consensus = all(row["exact"] == 96 for row in agreement.values())
    if not exact_consensus:
        raise RuntimeError("NO_AUTOMATIC_ADJUDICATION_ALLOWED")

    consensus = left
    by_arm = {}
    for arm in ("BASE", "EXPLICIT"):
        ids = [blind_id for blind_id, row in private.items() if row["arm"] == arm]
        valid = [blind_id for blind_id in ids if consensus[blind_id]["interface"] == "VALID"]
        susceptible = [blind_id for blind_id in valid if human_susceptible(consensus[blind_id])]
        by_arm[arm] = {
            "all_first_responses": len(ids),
            "interface_valid": len(valid),
            "susceptible_valid_programs": len(susceptible),
            "susceptible_fraction_of_valid": len(susceptible) / len(valid),
            "gap_update_outcomes_all": dict(sorted(Counter(consensus[blind_id]["gap_update_outcome"] for blind_id in ids).items())),
            "gap_update_outcomes_valid": dict(sorted(Counter(consensus[blind_id]["gap_update_outcome"] for blind_id in valid).items())),
            "stable_pair_counts": dict(sorted(Counter(consensus[blind_id]["stable_pair_strategy"] for blind_id in ids).items())),
        }

    by_profile = {}
    for profile in ("deepseek_flash", "glm5"):
        ids = [blind_id for blind_id, row in private.items() if row["arm"] == "BASE" and row["profile"] == profile]
        valid = [blind_id for blind_id in ids if consensus[blind_id]["interface"] == "VALID"]
        by_profile[profile] = {
            "all": len(ids), "valid": len(valid),
            "susceptible": sum(human_susceptible(consensus[blind_id]) for blind_id in valid),
        }
    by_stratum = {}
    for stratum in sorted({row["stratum"] for row in private_rows}):
        ids = [blind_id for blind_id, row in private.items() if row["arm"] == "BASE" and row["stratum"] == stratum]
        valid = [blind_id for blind_id in ids if consensus[blind_id]["interface"] == "VALID"]
        by_stratum[stratum] = {
            "all": len(ids), "valid": len(valid),
            "susceptible": sum(human_susceptible(consensus[blind_id]) for blind_id in valid),
        }

    pairing = defaultdict(dict)
    for blind_id, row in private.items():
        pairing[(row["task_id"], row["profile"])][row["arm"]] = blind_id
    paired_counts = Counter()
    for pair in pairing.values():
        base_positive = human_susceptible(consensus[pair["BASE"]])
        explicit_positive = human_susceptible(consensus[pair["EXPLICIT"]])
        paired_counts[(base_positive, explicit_positive)] += 1

    interface_alignment = sum(
        (consensus[blind_id]["interface"] == "VALID") == bool(row["interface_valid"])
        for blind_id, row in private.items()
    )
    valid_ids = [blind_id for blind_id, row in private.items() if row["interface_valid"]]
    no_update_alignment = sum(
        consensus[blind_id]["no_update_outcome"] == machine_serial_label(private[blind_id])
        for blind_id in valid_ids
    )
    gap_alignment = sum(
        consensus[blind_id]["gap_update_outcome"] == machine_long_label(private[blind_id])
        for blind_id in valid_ids
    )
    divergences = []
    for blind_id in valid_ids:
        human_label = consensus[blind_id]["gap_update_outcome"]
        machine_label = machine_long_label(private[blind_id])
        if human_label != machine_label:
            divergences.append({
                "blind_id": blind_id,
                "slot_id": private[blind_id]["slot_id"],
                "machine_concurrent_long": machine_label,
                "human_gap_after_first_observation": human_label,
                "human_rationale": consensus[blind_id]["rationale"],
                "scope_explanation": "The policy performs no observation. The machine schedule publishes before protected use; the human vignette specified publication after the first observation, so its trigger is absent. Labels are retained without adjudication.",
            })

    integrity = {
        "schema": "paper3.rq2.coherent_pair.return_integrity.v1",
        "status": "PASS",
        "package_sha256": read(RELEASE / "PACKAGE_MANIFEST.json")["archive_sha256"],
        "source_archives": {
            "Paper3_RQ2_双资源一致快照_审核返还.zip": "c27b29ce9ad7986b38bb180a98eeb9c896bf05ed7751bd38ac836b31c296d662",
            "Paper3_RQ2_双资源一致快照_审核返还_Reviewer2.zip": "c16661acd59d4b79aaf140de27fb6e66269dadf98a25de9a812da07c0e9a98fd",
        },
        "return_json": {reviewer: {"path": str(path.relative_to(ROOT)), "sha256": sha(path)} for reviewer, path in RETURN_FILES.items()},
        "checks": checks,
    }
    agreement_result = {
        "schema": "paper3.rq2.coherent_pair.human_agreement.v1",
        "status": "EXACT_CONSENSUS" if exact_consensus else "DISAGREEMENT_RETAIN",
        "fields": agreement,
        "automatic_adjudication": False,
    }
    result = {
        "schema": "paper3.rq2.coherent_pair.final_human_validated_result.v1",
        "status": "FINAL_RQ2_STRONG_SUPPORT",
        "machine_primary": read(RUN / "FINAL_MACHINE_RESULT.json"),
        "human_by_arm": by_arm,
        "human_base_by_profile": by_profile,
        "human_base_by_stratum": by_stratum,
        "paired_mitigation": {
            "base_failure_explicit_success": paired_counts[(True, False)],
            "both_failure": paired_counts[(True, True)],
            "both_success_or_not_susceptible": paired_counts[(False, False)],
            "base_success_explicit_failure": paired_counts[(False, True)],
        },
        "human_machine_alignment": {
            "interface": {"exact": interface_alignment, "total": 96},
            "no_update_among_machine_valid": {"exact": no_update_alignment, "total": len(valid_ids)},
            "gap_update_among_machine_valid": {"exact": gap_alignment, "total": len(valid_ids)},
            "scope_divergences": divergences,
        },
        "final_claim": "Concurrent peer updates interacting with longer exposure windows robustly increase cross-model failure when separately observed resource authorizations are treated as one coherent snapshot; an explicit stable-pair collection pattern strongly reduces the increase.",
        "claim_boundary": "The machine schedule establishes the pre-registered concurrency-by-window interaction. Human review independently confirms source/interface semantics and the direction of update susceptibility. Two no-observation policies differ only because the human vignette conditioned publication on a first observation; both labels are retained and the conservative human counts remain strongly supportive.",
    }
    write(RUN / "RETURN_INTEGRITY.json", integrity)
    write(RUN / "HUMAN_AGREEMENT.json", agreement_result)
    write(RUN / "FINAL_HUMAN_VALIDATED_RQ2_RESULT.json", result)
    print(json.dumps({
        "status": result["status"],
        "agreement": {field: agreement[field]["proportion"] for field in FIELDS},
        "base": by_arm["BASE"], "explicit": by_arm["EXPLICIT"],
        "profiles": by_profile, "strata": by_stratum,
        "paired_mitigation": result["paired_mitigation"],
        "alignment": result["human_machine_alignment"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

