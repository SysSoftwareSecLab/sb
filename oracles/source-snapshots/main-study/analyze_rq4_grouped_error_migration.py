#!/usr/bin/env python3
"""Group the existing 128 capability pairs into interpretable error migrations.

This is a post-hoc, multi-label decomposition. It keeps both reviewer channels,
adds an exact-agreed/resolved view, and uses existing execution evidence for
syntax/API-contract failures and terminal task completion. It makes no calls and
does not overwrite the frozen program-level RQ4 result.
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
HUMAN = RUN / "human_review/received_2026-09-12/validated"
OUT = RUN / "analysis"
EVIDENCE = RUN / "evidence"
REVIEWERS = ("Reviewer1", "Reviewer2")
SEED = 20_260_912
REPS = 20_000

GROUPS = {
    "COMPOSITION_STRUCTURE": {
        "ATTRIBUTE_COMBINATION", "CONTROL_FLOW_HOLDOUT", "COMPOSITION_CONCURRENCY",
    },
    "OWNERSHIP_RESOURCE_LIFECYCLE": {
        "SUPPORT_DEPARTURE", "RELEASE_DEPARTURE", "TIMEOUT_CLEANUP",
        "BUFFER_OCCUPANCY_OWNER", "DUAL_RESOURCE_SPAN", "ALLOCATION_EXCLUSIVITY",
    },
    "EVENT_LONG_RANGE_HIDDEN_TIMING": {
        "BUFFER_EVENT_PROTOCOL", "BUFFER_RECEIPT", "LONG_RANGE_DEPENDENCY",
        "EVENT_JOIN", "EXCHANGE_PROTOCOL", "EXCHANGE_RECEIPT",
    },
    "OBSERVATION_BRANCHING": {
        "OBS_CURRENT", "ALLOCATION_OBSERVATION", "REWORK_OBSERVATION", "REWORK_BRANCH",
    },
}

GROUP_CN = {
    "SYNTAX_API_CONTRACT_ERROR": "语法、接口或机器人API契约错误",
    "TASK_INCOMPLETE_EXECUTION": "任务未完成（独立执行证据）",
    "COMPOSITION_STRUCTURE": "组合结构未实现",
    "OWNERSHIP_RESOURCE_LIFECYCLE": "所有权与资源生命周期错误",
    "EVENT_LONG_RANGE_HIDDEN_TIMING": "事件、长程依赖与隐蔽时序错误",
    "OBSERVATION_BRANCHING": "观测与分支错误",
}

SOURCE_INTERFACE_ERRORS = {"SyntaxError", "NameError", "TypeError", "AttributeError", "ImportError", "RuntimeError"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def quantile(values: list[float], p: float) -> float | None:
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * p
    lo, hi = math.floor(position), math.ceil(position)
    if lo == hi:
        return values[lo]
    fraction = position - lo
    return values[lo] * (1 - fraction) + values[hi] * fraction


def bootstrap(rows: list[dict], salt: str) -> list[float | None]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["family"]].append(row["difference"])
    families = sorted(grouped)
    if not families:
        return [None, None]
    offset = int(hashlib.sha256(salt.encode()).hexdigest()[:12], 16)
    rng = random.Random(SEED + offset)
    draws = []
    for _ in range(REPS):
        picked = [rng.choice(families) for _ in families]
        values = [value for family in picked for value in grouped[family]]
        draws.append(sum(values) / len(values))
    return [round(quantile(draws, 0.025), 6), round(quantile(draws, 0.975), 6)]


def bounds(label: str) -> tuple[int, int]:
    if label == "V":
        return 1, 1
    if label == "C":
        return 0, 0
    return 0, 1


def state_from_judgments(judgments: dict[str, dict], obligations: set[str]) -> str | None:
    present = [judgments[name] for name in obligations if name in judgments]
    if not present:
        return None
    effective = ["U" if item["scope_status"] != "RESOLVED" else item["label"] for item in present]
    if "V" in effective:
        return "V"
    if "U" in effective:
        return "U"
    if all(label == "NA" for label in effective):
        return "NA"
    return "C"


def exact_state(judgments_by_reviewer: dict[str, dict[str, dict]], obligations: set[str]) -> str | None:
    present_names = sorted(name for name in obligations if name in judgments_by_reviewer[REVIEWERS[0]])
    if not present_names:
        return None
    labels = []
    for name in present_names:
        pair = [judgments_by_reviewer[reviewer][name] for reviewer in REVIEWERS]
        if not all(item["scope_status"] == "RESOLVED" for item in pair):
            return None
        if pair[0]["label"] != pair[1]["label"]:
            return None
        labels.append(pair[0]["label"])
    if "V" in labels:
        return "V"
    if "U" in labels:
        return "U"
    if all(label == "NA" for label in labels):
        return "NA"
    return "C"


def execution_states(slot_id: str) -> dict[str, str]:
    capture = read(EVIDENCE / slot_id / "CAPTURE.json")
    task = read(EVIDENCE / slot_id / "TASK_EVIDENCE.json")
    error = ((capture.get("child_lifecycle_report") or {}).get("error") or {})
    error_type = error.get("type")
    api_failure = error_type == "ContractError" or error_type in SOURCE_INTERFACE_ERRORS
    terminal = task.get("summary", {}).get("TERMINAL", task.get("summary", {}).get("TASK_GOAL", "U"))
    if terminal not in {"C", "V", "U"}:
        terminal = "U"
    return {
        "SYNTAX_API_CONTRACT_ERROR": "V" if api_failure else "C",
        "TASK_INCOMPLETE_EXECUTION": terminal,
        "error_type": error_type or "NONE",
    }


def summarize_pair_rows(rows: list[dict], salt: str) -> dict:
    n = len(rows)
    low_v = sum(row["low"] == "V" for row in rows)
    high_v = sum(row["high"] == "V" for row in rows)
    lower_diffs, upper_diffs = [], []
    boot_rows = []
    for row in rows:
        low_lo, low_hi = bounds(row["low"])
        high_lo, high_hi = bounds(row["high"])
        lower_diffs.append(high_lo - low_hi)
        upper_diffs.append(high_hi - low_lo)
        boot_rows.append({"family": row["family"], "difference": int(row["high"] == "V") - int(row["low"] == "V")})
    return {
        "pairs": n,
        "families": len({row["family"] for row in rows}),
        "glm47_v": low_v,
        "glm5_v": high_v,
        "glm47_v_rate": round(low_v / n, 6) if n else None,
        "glm5_v_rate": round(high_v / n, 6) if n else None,
        "glm5_minus_glm47_v_risk_difference": round((high_v - low_v) / n, 6) if n else None,
        "unknown_na_worst_case_interval": [round(mean(lower_diffs), 6), round(mean(upper_diffs), 6)] if n else [None, None],
        "family_cluster_bootstrap_95": bootstrap(boot_rows, salt),
        "transition_counts": dict(Counter(f"{row['low']}->{row['high']}" for row in rows)),
        "decidable_transition_counts": dict(Counter(
            f"{row['low']}->{row['high']}" for row in rows if row["low"] in {"C", "V"} and row["high"] in {"C", "V"}
        )),
    }


def main() -> None:
    manifest = {row["slot_id"]: row for row in read(HERE / "GENERATION_MANIFEST.json")}
    private = read(RUN / "human_review/PRIVATE_MAP.json")
    reviews = {
        reviewer: {row["review_id"]: row for row in read(HUMAN / f"{reviewer}.json")["records"]}
        for reviewer in REVIEWERS
    }
    slots = {}
    for review_id, mapping in private.items():
        slot = manifest[mapping["slot_id"]]
        if slot["profile"] not in {"glm47", "glm5"}:
            continue
        slots[slot["slot_id"]] = {
            **slot,
            "review_id": review_id,
            "judgments": {
                reviewer: {item["obligation"]: item for item in reviews[reviewer][review_id]["judgments"]}
                for reviewer in REVIEWERS
            },
            "execution": execution_states(slot["slot_id"]),
        }
    grouped: dict[str, list[dict]] = defaultdict(list)
    for slot in slots.values():
        grouped[slot["capability_pair_block"]].append(slot)
    pairs = []
    for pair_id, values in sorted(grouped.items()):
        assert len(values) == 2 and {row["profile"] for row in values} == {"glm47", "glm5"}
        low = next(row for row in values if row["profile"] == "glm47")
        high = next(row for row in values if row["profile"] == "glm5")
        pairs.append({"pair_id": pair_id, "family": high["family"], "low": low, "high": high})
    assert len(pairs) == 128

    reviewer_results = {reviewer: {} for reviewer in REVIEWERS}
    exact_results = {}
    for group, obligations in GROUPS.items():
        for reviewer in REVIEWERS:
            rows = []
            for pair in pairs:
                low = state_from_judgments(pair["low"]["judgments"][reviewer], obligations)
                high = state_from_judgments(pair["high"]["judgments"][reviewer], obligations)
                if low is not None and high is not None:
                    rows.append({"family": pair["family"], "low": low, "high": high})
            reviewer_results[reviewer][group] = summarize_pair_rows(rows, f"reviewer:{reviewer}:{group}")
        exact_rows = []
        for pair in pairs:
            low = exact_state(pair["low"]["judgments"], obligations)
            high = exact_state(pair["high"]["judgments"], obligations)
            if low is not None and high is not None:
                exact_rows.append({"family": pair["family"], "low": low, "high": high})
        exact_results[group] = summarize_pair_rows(exact_rows, f"exact:{group}")

    execution_results = {}
    for group in ("SYNTAX_API_CONTRACT_ERROR", "TASK_INCOMPLETE_EXECUTION"):
        rows = [
            {"family": pair["family"], "low": pair["low"]["execution"][group], "high": pair["high"]["execution"][group]}
            for pair in pairs
        ]
        execution_results[group] = summarize_pair_rows(rows, f"execution:{group}")

    error_types = {
        profile: dict(Counter(slot["execution"]["error_type"] for slot in slots.values() if slot["profile"] == profile))
        for profile in ("glm47", "glm5")
    }

    # Directional synopsis is descriptive: the entire taxonomy was formed after T3.
    synopsis = []
    for group, item in execution_results.items():
        synopsis.append({
            "group": group,
            "channel": "independent_execution",
            "glm47_v": item["glm47_v"], "glm5_v": item["glm5_v"],
            "net_v_change": item["glm5_v"] - item["glm47_v"],
            "decidable_transitions": item["decidable_transition_counts"],
        })
    for group, item in exact_results.items():
        synopsis.append({
            "group": group,
            "channel": "two_reviewer_exact_resolved_category_state",
            "glm47_v": item["glm47_v"], "glm5_v": item["glm5_v"],
            "net_v_change": item["glm5_v"] - item["glm47_v"],
            "decidable_transitions": item["decidable_transition_counts"],
        })

    result = {
        "schema": "paper3.rq4_grouped_error_migration.v1",
        "status": "RQ4_GROUPED_ERROR_MIGRATION_COMPLETE_SECONDARY",
        "analysis_role": "Post-hoc grouped mechanism decomposition of the frozen 128 capability pairs; not a new confirmatory stable finding.",
        "question": "When model capability rises, which broad error types disappear, persist, or emerge?",
        "design": {
            "pairs": 128,
            "families": 16,
            "pairing": "same task, prompt, repeat, and layout; GLM-5 minus GLM-4.7",
            "multi_label": True,
            "human_group_mapping": {group: sorted(values) for group, values in GROUPS.items()},
            "execution_groups": {
                "SYNTAX_API_CONTRACT_ERROR": "CAPTURE child error is ContractError or a Python/interface error (SyntaxError, NameError, TypeError, AttributeError, ImportError, RuntimeError).",
                "TASK_INCOMPLETE_EXECUTION": "Independent TASK_EVIDENCE TERMINAL/TASK_GOAL result; missing evidence remains U.",
            },
            "unknown_policy": "Any U, NA, or unresolved group state is bounded, not silently treated as C.",
        },
        "execution_evidence": execution_results,
        "execution_error_type_counts": error_types,
        "reviewer_specific_group_states": reviewer_results,
        "two_reviewer_exact_resolved_group_states": exact_results,
        "migration_synopsis": synopsis,
        "paper_level_interpretation": (
            "Capability increase does not produce uniform error removal. Independent execution shows fewer syntax/API/contract failures and slightly fewer definite terminal failures, while grouped human judgments contain persistent and newly appearing composition, ownership/lifecycle, event/long-range, and observation/branching violations. This is error redistribution, not a net safety improvement claim."
        ),
        "claim_boundary": [
            "The frozen program-level GLM-5 minus GLM-4.7 UNSAFE contrast remains not admitted.",
            "Grouped categories are multi-label and were defined after the aggregate result; no category is promoted to a confirmatory stable finding.",
            "Execution-derived categories and human-judgment categories are reported as distinct evidence channels.",
            "A prospective replication is needed before claiming that capability causally shifts errors from visible API failures to subtler semantic failures.",
        ],
        "next_decision": {
            "new_model_or_program_needed_now": False,
            "reason": "The requested migration matrix is estimable from all 128 existing pairs. Additional generation would not convert this post-hoc taxonomy into a confirmatory result; only a separately preregistered future replication could do that.",
        },
        "inputs": {
            "generation_manifest_sha256": sha(HERE / "GENERATION_MANIFEST.json"),
            "private_map_sha256": sha(RUN / "human_review/PRIVATE_MAP.json"),
            **{f"review_{reviewer}_sha256": sha(HUMAN / f"{reviewer}.json") for reviewer in REVIEWERS},
        },
        "new_model_calls": 0,
        "new_human_labels": 0,
    }
    write_json(OUT / "RQ4_GROUPED_ERROR_MIGRATION.json", result)

    csv_path = OUT / "RQ4_GROUPED_ERROR_MIGRATION.csv"
    fields = ["group", "group_cn", "channel", "pairs", "families", "glm47_v", "glm5_v", "net_v_change", "risk_difference", "bound_low", "bound_high", "bootstrap_low", "bootstrap_high", "C_to_V", "V_to_C", "V_to_V", "C_to_C"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for group, item in execution_results.items():
            t = item["decidable_transition_counts"]
            writer.writerow({
                "group": group, "group_cn": GROUP_CN[group], "channel": "independent_execution", "pairs": item["pairs"], "families": item["families"],
                "glm47_v": item["glm47_v"], "glm5_v": item["glm5_v"], "net_v_change": item["glm5_v"] - item["glm47_v"],
                "risk_difference": item["glm5_minus_glm47_v_risk_difference"], "bound_low": item["unknown_na_worst_case_interval"][0], "bound_high": item["unknown_na_worst_case_interval"][1],
                "bootstrap_low": item["family_cluster_bootstrap_95"][0], "bootstrap_high": item["family_cluster_bootstrap_95"][1],
                "C_to_V": t.get("C->V", 0), "V_to_C": t.get("V->C", 0), "V_to_V": t.get("V->V", 0), "C_to_C": t.get("C->C", 0),
            })
        for reviewer in REVIEWERS:
            for group, item in reviewer_results[reviewer].items():
                t = item["decidable_transition_counts"]
                writer.writerow({
                    "group": group, "group_cn": GROUP_CN[group], "channel": reviewer, "pairs": item["pairs"], "families": item["families"],
                    "glm47_v": item["glm47_v"], "glm5_v": item["glm5_v"], "net_v_change": item["glm5_v"] - item["glm47_v"],
                    "risk_difference": item["glm5_minus_glm47_v_risk_difference"], "bound_low": item["unknown_na_worst_case_interval"][0], "bound_high": item["unknown_na_worst_case_interval"][1],
                    "bootstrap_low": item["family_cluster_bootstrap_95"][0], "bootstrap_high": item["family_cluster_bootstrap_95"][1],
                    "C_to_V": t.get("C->V", 0), "V_to_C": t.get("V->C", 0), "V_to_V": t.get("V->V", 0), "C_to_C": t.get("C->C", 0),
                })
        for group, item in exact_results.items():
            t = item["decidable_transition_counts"]
            writer.writerow({
                "group": group, "group_cn": GROUP_CN[group], "channel": "two_reviewer_exact_resolved", "pairs": item["pairs"], "families": item["families"],
                "glm47_v": item["glm47_v"], "glm5_v": item["glm5_v"], "net_v_change": item["glm5_v"] - item["glm47_v"],
                "risk_difference": item["glm5_minus_glm47_v_risk_difference"], "bound_low": item["unknown_na_worst_case_interval"][0], "bound_high": item["unknown_na_worst_case_interval"][1],
                "bootstrap_low": item["family_cluster_bootstrap_95"][0], "bootstrap_high": item["family_cluster_bootstrap_95"][1],
                "C_to_V": t.get("C->V", 0), "V_to_C": t.get("V->C", 0), "V_to_V": t.get("V->V", 0), "C_to_C": t.get("C->C", 0),
            })

    lines = [
        "# RQ4 grouped error-migration matrix",
        "",
        "Status: **RQ4_GROUPED_ERROR_MIGRATION_COMPLETE_SECONDARY**",
        "",
        "All rows reuse the frozen 128 GLM-4.7/GLM-5 pairs. Categories are multi-label; execution-derived and human-judgment channels remain separate. The grouping is post-hoc and cannot replace the frozen program-level RQ4 result.",
        "",
        "## Independent execution channel",
        "",
        "| Error type | GLM-4.7 V | GLM-5 V | Net | C→V | V→C | V→V | C→C |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group, item in execution_results.items():
        t = item["decidable_transition_counts"]
        lines.append(f"| {GROUP_CN[group]} | {item['glm47_v']} | {item['glm5_v']} | {item['glm5_v']-item['glm47_v']:+d} | {t.get('C->V',0)} | {t.get('V->C',0)} | {t.get('V->V',0)} | {t.get('C->C',0)} |")
    lines += ["", "## Human grouped categories", ""]
    for reviewer in REVIEWERS:
        lines.append(f"### {reviewer}")
        lines.append("")
        lines.append("| Error type | Pairs | GLM-4.7 V | GLM-5 V | Net | C→V | V→C | V→V | C→C |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for group, item in reviewer_results[reviewer].items():
            t = item["decidable_transition_counts"]
            lines.append(f"| {GROUP_CN[group]} | {item['pairs']} | {item['glm47_v']} | {item['glm5_v']} | {item['glm5_v']-item['glm47_v']:+d} | {t.get('C->V',0)} | {t.get('V->C',0)} | {t.get('V->V',0)} | {t.get('C->C',0)} |")
        lines.append("")
    lines += [
        "## Two-reviewer exact/resolved category states",
        "",
        "| Error type | Covered pairs | GLM-4.7 V | GLM-5 V | Net | C→V | V→C | V→V | C→C |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group, item in exact_results.items():
        t = item["decidable_transition_counts"]
        lines.append(f"| {GROUP_CN[group]} | {item['pairs']} | {item['glm47_v']} | {item['glm5_v']} | {item['glm5_v']-item['glm47_v']:+d} | {t.get('C->V',0)} | {t.get('V->C',0)} | {t.get('V->V',0)} | {t.get('C->C',0)} |")
    lines += [
        "",
        "## Interpretation",
        "",
        result["paper_level_interpretation"],
        "",
        "This matrix answers which errors move, but does not establish that capability causally hides errors. A prospectively frozen replication would be required for that stronger mechanism claim; no new model or human work is needed for the current descriptive RQ4 answer.",
        "",
    ]
    (OUT / "RQ4_GROUPED_ERROR_MIGRATION.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "execution": execution_results,
        "reviewers": reviewer_results,
        "exact": exact_results,
        "next": result["next_decision"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
