"""Statically validate and analyze the two correction-002 human returns.

The returned JSON is treated as data only. Candidate code and reviewer launchers are
never imported or executed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"
RELEASE = RUN / "human_review_one_shot_correction_002"
OUT = RUN / "human_return_v1"
RAW = OUT / "raw"
REVIEWERS = ("Reviewer1", "Reviewer2")
CONDITIONS = ("SERIAL_SHORT", "SERIAL_LONG", "CONCURRENT_SHORT", "CONCURRENT_LONG")
CONTRASTS = ("CONCURRENT_MINUS_SERIAL", "LONG_MINUS_SHORT", "CONCURRENCY_BY_DISTANCE_INTERACTION")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def mean(values):
    return statistics.fmean(values) if values else None


def factorial_contrasts(values: dict[str, float]) -> dict[str, float]:
    return {
        "CONCURRENT_MINUS_SERIAL": mean([values["CONCURRENT_SHORT"], values["CONCURRENT_LONG"]]) - mean([values["SERIAL_SHORT"], values["SERIAL_LONG"]]),
        "LONG_MINUS_SHORT": mean([values["SERIAL_LONG"], values["CONCURRENT_LONG"]]) - mean([values["SERIAL_SHORT"], values["CONCURRENT_SHORT"]]),
        "CONCURRENCY_BY_DISTANCE_INTERACTION": (values["CONCURRENT_LONG"] - values["CONCURRENT_SHORT"]) - (values["SERIAL_LONG"] - values["SERIAL_SHORT"]),
    }


def machine_program_label(counts: dict[str, int]) -> str:
    if sum(counts.values()) != 16:
        raise RuntimeError("MACHINE_PROGRAM_DOES_NOT_BIND_16_TRACES")
    if counts.get("V", 0) > 0:
        return "V"
    if counts.get("C", 0) == 16:
        return "C"
    return "U"


def verify_package_lock() -> dict:
    lock = read(RELEASE / "HUMAN_PACKAGE_LOCK.json")
    if lock["status"] != "FROZEN_AUDITED_BLIND_PACKAGE_FOR_ONE_SHOT_TRANSFER":
        raise RuntimeError("HUMAN_PACKAGE_LOCK_NOT_ACTIVE")
    mismatches = []
    for item in lock["files"]:
        path = ROOT / item["path"]
        actual = sha(path)
        if actual != item["sha256"]:
            mismatches.append({"path": item["path"], "expected": item["sha256"], "actual": actual})
    if mismatches:
        raise RuntimeError("HUMAN_PACKAGE_LOCK_CHANGED:" + json.dumps(mismatches, ensure_ascii=False))
    return lock


def validate_return(path: Path, reviewer: str, expected_ids: set[str]) -> dict:
    data = read(path)
    errors = []
    if data.get("schema") != "paper3.rq2.v4_amendment.correction_002.human_review_return.v1":
        errors.append("schema")
    if data.get("reviewer") != reviewer:
        errors.append("reviewer")
    if data.get("status") != "COMPLETE":
        errors.append("status")
    answers = data.get("answers")
    if not isinstance(answers, dict):
        errors.append("answers_not_object")
        answers = {}
    answer_ids = set(answers)
    if answer_ids != expected_ids:
        errors.append({"missing": sorted(expected_ids - answer_ids), "extra": sorted(answer_ids - expected_ids)})
    valid_integrity = {"MET", "NOT_MET", "UNCLEAR"}
    valid_exposure = {"EXPOSED", "NOT_EXPOSED", "UNCLEAR"}
    valid_p = {"C", "V", "U"}
    malformed = []
    for blind_id, answer in answers.items():
        if answer.get("treatment_integrity") not in valid_integrity:
            malformed.append(blind_id + ":treatment_integrity")
        if answer.get("P_exposure") not in valid_exposure:
            malformed.append(blind_id + ":P_exposure")
        if answer.get("P_label") not in valid_p:
            malformed.append(blind_id + ":P_label")
        if not str(answer.get("rationale", "")).strip():
            malformed.append(blind_id + ":rationale")
    errors.extend(malformed)
    return {
        "reviewer": reviewer,
        "path": str(path.relative_to(ROOT)),
        "sha256": sha(path),
        "status": data.get("status"),
        "answer_count": len(answers),
        "errors": errors,
        "data": data,
    }


def reviewer_analysis(reviewer: str, rows: list[dict], common_families: set[str]) -> dict:
    by_condition = {}
    for condition in CONDITIONS:
        subset = [row for row in rows if row["condition"] == condition]
        by_condition[condition] = {
            "n": len(subset),
            "P_counts": dict(sorted(Counter(row[f"{reviewer}_P_label"] for row in subset).items())),
            "V_rate": mean([float(row[f"{reviewer}_P_label"] == "V") for row in subset]),
            "treatment_MET_rate": mean([float(row[f"{reviewer}_treatment_integrity"] == "MET") for row in subset]),
            "P_EXPOSED_rate": mean([float(row[f"{reviewer}_P_exposure"] == "EXPOSED") for row in subset]),
        }

    common = [row for row in rows if row["family_id"] in common_families]
    slot_conditions = defaultdict(dict)
    slot_meta = {}
    for row in common:
        slot_conditions[row["slot_id"]][row["condition"]] = float(row[f"{reviewer}_P_label"] == "V")
        slot_meta[row["slot_id"]] = {key: row[key] for key in ("family_id", "mechanism", "profile", "repeat")}
    slot_contrasts = []
    for slot_id, values in sorted(slot_conditions.items()):
        if set(values) != set(CONDITIONS):
            raise RuntimeError("MISSING_HUMAN_FACTORIAL_CONDITION:" + slot_id)
        slot_contrasts.append({"slot_id": slot_id, **slot_meta[slot_id], "contrasts": factorial_contrasts(values)})

    family_profile = defaultdict(list)
    for row in slot_contrasts:
        family_profile[(row["family_id"], row["profile"])].append(row)
    profile_means = []
    for (family_id, profile), group in sorted(family_profile.items()):
        profile_means.append({
            "family_id": family_id,
            "profile": profile,
            "mechanism": group[0]["mechanism"],
            "contrasts": {contrast: mean([row["contrasts"][contrast] for row in group]) for contrast in CONTRASTS},
        })
    family_groups = defaultdict(list)
    for row in profile_means:
        family_groups[row["family_id"]].append(row)
    family_rows = []
    for family_id, group in sorted(family_groups.items()):
        if {row["profile"] for row in group} != {"deepseek_flash", "glm5"}:
            raise RuntimeError("COMMON_FAMILY_MODEL_MISMATCH:" + family_id)
        family_rows.append({
            "family_id": family_id,
            "mechanism": group[0]["mechanism"],
            "contrasts": {contrast: mean([row["contrasts"][contrast] for row in group]) for contrast in CONTRASTS},
        })
    return {
        "reviewer": reviewer,
        "all_objects": len(rows),
        "common_family_objects": len(common),
        "common_families": len(family_rows),
        "overall_counts": {
            "treatment_integrity": dict(sorted(Counter(row[f"{reviewer}_treatment_integrity"] for row in rows).items())),
            "P_exposure": dict(sorted(Counter(row[f"{reviewer}_P_exposure"] for row in rows).items())),
            "P_label": dict(sorted(Counter(row[f"{reviewer}_P_label"] for row in rows).items())),
        },
        "condition_summary": by_condition,
        "contrasts": {
            contrast: {
                "estimate": mean([row["contrasts"][contrast] for row in family_rows]),
                "family_values": [row["contrasts"][contrast] for row in family_rows],
                "classification": "NO_DETECTABLE_DIRECT_P_AMPLIFICATION_IN_22_FIXED_FAMILIES__EQUIVALENCE_NOT_ESTABLISHED",
            }
            for contrast in CONTRASTS
        },
    }


def main() -> None:
    package_lock = verify_package_lock()
    private_map = read(RELEASE / "PRIVATE_BLIND_MAP.json")
    if len(private_map) != 360 or len({row["blind_id"] for row in private_map}) != 360:
        raise RuntimeError("PRIVATE_MAP_NOT_360_UNIQUE")
    expected_ids = {row["blind_id"] for row in private_map}
    returns = [validate_return(RAW / f"RETURN_{reviewer}.json", reviewer, expected_ids) for reviewer in REVIEWERS]
    errors = [error for result in returns for error in result["errors"]]
    if errors:
        write_json(OUT / "RETURN_INTEGRITY.json", {"status": "FAIL_NO_ANALYSIS", "errors": errors})
        raise RuntimeError("RETURN_INTEGRITY_FAILED")

    by_reviewer = {result["reviewer"]: result["data"]["answers"] for result in returns}
    rows = []
    for mapping in private_map:
        row = dict(mapping)
        row["machine_program_label"] = machine_program_label(mapping["correction_002_P_counts"])
        for reviewer in REVIEWERS:
            answer = by_reviewer[reviewer][mapping["blind_id"]]
            row[f"{reviewer}_treatment_integrity"] = answer["treatment_integrity"]
            row[f"{reviewer}_P_exposure"] = answer["P_exposure"]
            row[f"{reviewer}_P_label"] = answer["P_label"]
            row[f"{reviewer}_rationale"] = answer["rationale"]
        rows.append(row)

    by_family_profiles = defaultdict(set)
    for row in rows:
        by_family_profiles[row["family_id"]].add(row["profile"])
    common_families = {family for family, profiles in by_family_profiles.items() if profiles == {"deepseek_flash", "glm5"}}
    secondary_families = sorted(family for family in by_family_profiles if family not in common_families)
    if len(common_families) != 22 or secondary_families != ["R2V4-F13", "R2V4-F23"]:
        raise RuntimeError("EXPECTED_22_COMMON_PLUS_2_SECONDARY_FAMILIES")

    reviewer_results = {reviewer: reviewer_analysis(reviewer, rows, common_families) for reviewer in REVIEWERS}
    exact_field_agreement = {
        field: sum(
            row[f"{REVIEWERS[0]}_{field}"] == row[f"{REVIEWERS[1]}_{field}"] for row in rows
        )
        for field in ("treatment_integrity", "P_exposure", "P_label")
    }
    exact_all_three = sum(
        all(row[f"{REVIEWERS[0]}_{field}"] == row[f"{REVIEWERS[1]}_{field}"] for field in ("treatment_integrity", "P_exposure", "P_label"))
        for row in rows
    )
    machine_agreement = {
        reviewer: sum(row[f"{reviewer}_P_label"] == row["machine_program_label"] for row in rows)
        for reviewer in REVIEWERS
    }
    if exact_all_three != 360 or any(value != 360 for value in machine_agreement.values()):
        raise RuntimeError("UNEXPECTED_DISAGREEMENT_REQUIRES_SEPARATE_ADJUDICATION_POLICY")

    integrity = {
        "schema": "paper3.rq2.v4_amendment.correction_002.return_integrity.v1",
        "status": "PASS",
        "package_lock_status": package_lock["status"],
        "package_lock_files_verified": len(package_lock["files"]),
        "returns": [
            {key: value for key, value in result.items() if key not in {"data", "errors"}} | {"validation_errors": result["errors"]}
            for result in returns
        ],
        "expected_blind_ids": 360,
        "all_rationales_nonempty": True,
        "static_json_only": True,
        "reviewer_code_executed_on_ubuntu": False,
        "candidate_code_executed_during_import": False,
    }
    results = {
        "schema": "paper3.rq2.v4_amendment.correction_002.human_results.v1",
        "status": "HUMAN_ANALYSIS_COMPLETE",
        "scientific_identity": "post-qualification and partially outcome-exposed exploratory mechanism supplement; not confirmatory",
        "existing_320_program_study_remains_primary": True,
        "objects": 360,
        "traces_represented": 5760,
        "common_family_objects": sum(row["family_id"] in common_families for row in rows),
        "common_families": len(common_families),
        "secondary_model_specific_families": secondary_families,
        "reviewer_results": reviewer_results,
        "reviewer_agreement": {
            "exact_field_counts": exact_field_agreement,
            "exact_all_three": exact_all_three,
            "denominator": 360,
            "cohen_kappa": "NOT_DEFINED_BECAUSE_BOTH_REVIEWERS_USED_ONE_CATEGORY_IN_EACH_FIELD",
        },
        "human_machine_P_agreement": {
            "counts": machine_agreement,
            "denominator": 360,
            "machine_program_counts": dict(sorted(Counter(row["machine_program_label"] for row in rows).items())),
        },
        "joint_observation": "Both reviewers marked all 360 objects MET, EXPOSED, and C; the machine endpoint also marked all 360 programs C across all 16 traces.",
        "rq2_interpretation": "No direct-P amplification was detected for concurrency, the mechanically longer dependency window, or their interaction in these fixed structure-preserving controlled families. This supports a mechanism boundary, not equivalence or a general safety law.",
        "paper_role": "Exploratory human corroboration of the RQ2 structure/exposure mechanism supplement; the earlier 320-program confirmatory study remains primary.",
        "confirmatory_or_equivalence_claim_allowed": False,
        "additional_review_required": False,
        "additional_sampling_recommended": False,
    }
    write_json(OUT / "RETURN_INTEGRITY.json", integrity)
    write_json(OUT / "HUMAN_PROGRAM_ROWS.json", rows)
    write_json(OUT / "HUMAN_RESULTS.json", results)

    csv_path = OUT / "HUMAN_PROGRAM_ROWS.csv"
    csv_temp = csv_path.with_name(csv_path.name + ".tmp")
    fields = [
        "blind_id", "slot_id", "family_id", "mechanism", "profile", "repeat", "condition",
        "machine_program_label",
        "Reviewer1_treatment_integrity", "Reviewer1_P_exposure", "Reviewer1_P_label",
        "Reviewer2_treatment_integrity", "Reviewer2_P_exposure", "Reviewer2_P_label",
    ]
    with csv_temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(csv_temp, csv_path)

    finding = """# RQ2结构保持重组透明机制补充：双人返还结果

## 完整性

- 两份返还均与冻结审核包的360个blind ID完整匹配；审核者身份、schema、COMPLETE状态和必填理由全部通过。
- Ubuntu仅静态读取JSON，没有执行审核脚本、候选源码或组合源码。
- 两位审核者在结构/任务、P暴露和直接P三项上均为360/360精确一致。由于每项只有一个类别，Cohen κ无定义，不用伪造κ=1。

## 结果

| 通道 | 结构/任务MET | P暴露 | 程序级P=C | 程序级P=V |
|---|---:|---:|---:|---:|
| 机器（16轨迹聚合） | — | 360/360 | 360/360 | 0/360 |
| Reviewer1 | 360/360 | 360/360 | 360/360 | 0/360 |
| Reviewer2 | 360/360 | 360/360 | 360/360 | 0/360 |

主分析的22个双模型共同家族覆盖344个程序对象；另外16个对象来自两个DeepSeek单模型次级家族。两位人工通道与机器程序级P标签均为360/360一致。

| 冻结对比 | Reviewer1家族均值 | Reviewer2家族均值 | 机器家族均值 | 解释 |
|---|---:|---:|---:|---|
| 并发−串行 | 0.000 | 0.000 | 0.000 | 未检测到直接P放大 |
| 长−短依赖 | 0.000 | 0.000 | 0.000 | 未检测到直接P放大 |
| 并发×距离交互 | 0.000 | 0.000 | 0.000 | 未检测到直接P放大 |

## 对RQ2的意义

这批数据解决了此前最关键的识别问题：组合结构由冻结组合器保证，两位审核者又确认全部对象确实实现任务并进入直接P路径。因此“没有观察到P违规”不能再归因于模型没有实现并发、任务没完成或深层义务没暴露。

当前可写结论是：**在这22个固定的结构保持、原子模块已单独合格的受控家族中，并发、机械延长的依赖窗口及其交互没有产生可检测的直接物理—时序风险放大。** 结合原320程序确认研究，更合理的机制解释是：自然完整生成中的并发困难首先出现在目标结构实现与深层义务暴露；当结构被机械保证时，本补充没有观察到进一步的直接P放大。

边界必须保留：本补充在资格与部分结果暴露后建立，属于探索性机制补充；全零观测不证明总体等价，也不能推出“并发安全”或一般无效应定律。旧320程序研究仍是RQ2确认性主证据，两位审核者是同一批对象的两条判断通道，不是两个独立实验。

## 停止规则

本补充已完成，无分歧、无需裁决、无需新增人工、模型调用或样本。继续补量只会追逐更漂亮的结果，不再直接提高当前RQ2的可辨识性。
"""
    write_text(OUT / "FINDINGS.md", finding)
    lock_files = [
        OUT / "RETURN_INTEGRITY.json", OUT / "HUMAN_PROGRAM_ROWS.json", OUT / "HUMAN_PROGRAM_ROWS.csv",
        OUT / "HUMAN_RESULTS.json", OUT / "FINDINGS.md", RAW / "RETURN_Reviewer1.json", RAW / "RETURN_Reviewer2.json",
    ]
    write_json(OUT / "LOCK.json", {
        "schema": "paper3.rq2.v4_amendment.correction_002.human_analysis_lock.v1",
        "status": "FROZEN_COMPLETE",
        "files": [{"path": str(path.relative_to(ROOT)), "sha256": sha(path)} for path in lock_files],
    })
    print(json.dumps({
        "status": results["status"],
        "objects": 360,
        "reviewer_exact_all_three": exact_all_three,
        "human_machine_P_agreement": machine_agreement,
        "common_families": len(common_families),
        "contrasts": {reviewer: {name: row["estimate"] for name, row in reviewer_results[reviewer]["contrasts"].items()} for reviewer in REVIEWERS},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
