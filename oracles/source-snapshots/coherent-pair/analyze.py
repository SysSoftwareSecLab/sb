from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN = ROOT / "05_formal" / "rq2_coherent_pair_confirmation_v1"

from coherent_runtime import CONDITIONS, SEEDS, run_policy, schedule, validate_source


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_freeze() -> dict:
    freeze = read(HERE / "SCIENTIFIC_FREEZE.json")
    if freeze["status"] != "FROZEN_BEFORE_ANY_NEW_CALL":
        raise RuntimeError("FREEZE_NOT_ACTIVE")
    for item in freeze["files"]:
        if sha(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError("FROZEN_FILE_CHANGED:" + item["path"])
    return freeze


def compile_candidate(source: str, task: dict):
    tree = validate_source(source, task)
    namespace = {"__builtins__": {}}
    exec(compile(tree, "frozen_candidate.py", "exec"), namespace)
    return namespace["consumer_policy"]


def condition_rates(rows: list[dict]) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["condition"]].append(row)
    return {
        condition: {
            "F": sum(row["F"] for row in values) / len(values),
            "V": sum(row["P"] == "V" for row in values) / len(values),
            "NE": sum(row["P"] == "NE" for row in values) / len(values),
            "S0": sum(row["P"] == "S0" for row in values) / len(values),
            "C": sum(row["P"] == "C" for row in values) / len(values),
        }
        for condition, values in grouped.items()
    }


def interaction(rates: dict, endpoint: str) -> float:
    return (
        rates["CONCURRENT_LONG"][endpoint]
        - rates["CONCURRENT_SHORT"][endpoint]
        - rates["SERIAL_LONG"][endpoint]
        + rates["SERIAL_SHORT"][endpoint]
    )


def mechanism_positive(rates: dict) -> bool:
    return (
        rates["SERIAL_SHORT"]["F"] == 0.0
        and rates["SERIAL_LONG"]["F"] == 0.0
        and 0.0 < rates["CONCURRENT_SHORT"]["F"] < 1.0
        and rates["CONCURRENT_LONG"]["F"] > rates["CONCURRENT_SHORT"]["F"]
    )


def precall() -> None:
    verify_freeze()
    tasks = read(HERE / "TASK_CATALOG.json")
    reference_all_c = True
    reference_rows = 0
    for family_index, task in enumerate(tasks):
        left, right = task["state_ids"]
        action = task["action_id"]

        async def reference(robot, cached_left, cached_right, left_id=left, right_id=right, action_id=action):
            left_first = await robot.observe_authorization(left_id)
            right_receipt = await robot.observe_authorization(right_id)
            left_second = await robot.observe_authorization(left_id)
            if left_first.coordination_generation == left_second.coordination_generation:
                left_receipt = left_first
            else:
                left_receipt = left_second
                right_receipt = await robot.observe_authorization(right_id)
            await robot.protected_action(action_id, left_receipt, right_receipt)

        rows = run_policy(reference, task, family_index)
        reference_rows += len(rows)
        reference_all_c = reference_all_c and all(row["P"] == "C" for row in rows)

    task = tasks[0]
    left, right = task["state_ids"]
    action = task["action_id"]

    async def stale(robot, cached_left, cached_right):
        await robot.protected_action(action, cached_left, cached_right)

    async def one_pass(robot, cached_left, cached_right):
        left_receipt = await robot.observe_authorization(left)
        right_receipt = await robot.observe_authorization(right)
        await robot.protected_action(action, left_receipt, right_receipt)

    async def fail_closed(robot, cached_left, cached_right):
        left_receipt = await robot.observe_authorization(left)
        right_receipt = await robot.observe_authorization(right)
        if left_receipt.coordination_generation == right_receipt.coordination_generation:
            await robot.protected_action(action, left_receipt, right_receipt)

    stale_rates = condition_rates(run_policy(stale, task, 0))
    one_pass_rates = condition_rates(run_policy(one_pass, task, 0))
    closed_rates = condition_rates(run_policy(fail_closed, task, 0))
    boundary = all([
        stale_rates["CONCURRENT_SHORT"]["V"] == 0.25,
        stale_rates["CONCURRENT_LONG"]["V"] == 1.0,
        one_pass_rates["CONCURRENT_SHORT"]["V"] == 0.25,
        one_pass_rates["CONCURRENT_LONG"]["V"] == 1.0,
        closed_rates["CONCURRENT_SHORT"]["NE"] == 0.25,
        closed_rates["CONCURRENT_LONG"]["NE"] == 1.0,
    ])
    result = {
        "schema": "paper3.rq2.coherent_pair_confirmation.precall.v1",
        "status": "PASS" if reference_all_c and boundary else "FAIL",
        "scientific_calls": 0,
        "reference_rows": reference_rows,
        "reference_all_C": reference_all_c,
        "stale_rates": stale_rates,
        "one_pass_rates": one_pass_rates,
        "fail_closed_rates": closed_rates,
        "oracle_boundary_pass": boundary,
    }
    write(RUN / "PRECALL_GATE.json", result)
    print(json.dumps(result, indent=2))


def evaluate_slots(slots: list[dict], tasks: dict, task_index: dict) -> tuple[list[dict], list[dict]]:
    rows = []
    programs = []
    for slot in slots:
        task = tasks[slot["task_id"]]
        folder = RUN / "generation" / slot["slot_id"]
        result = read(folder / "RESULT.json")
        candidate = folder / "candidate.py"
        valid = result.get("status") == "VALID_SOURCE" and candidate.exists()
        if valid:
            if result["source_sha256"] != sha(candidate):
                raise RuntimeError("SOURCE_CHANGED:" + slot["slot_id"])
            policy = compile_candidate(candidate.read_text(encoding="utf-8"), task)
            slot_rows = run_policy(policy, task, task_index[slot["task_id"]])
        else:
            slot_rows = []
            for condition in CONDITIONS:
                for seed in SEEDS:
                    trace = schedule(task_index[slot["task_id"]], condition, seed)
                    slot_rows.append({
                        "condition": condition, "seed": seed,
                        "risk_opportunity": trace["risk_opportunity"],
                        "causal_order": trace["causal_order"],
                        "schedule_sha256": trace["schedule_sha256"],
                        "event_log": [], "action_count": 0,
                        "error_type": "GENERATION_OR_INTERFACE_INVALID", "P": "S0", "F": 1,
                    })
        for row in slot_rows:
            rows.append({
                "slot_id": slot["slot_id"], "task_id": slot["task_id"],
                "stratum": slot["stratum"], "arm": slot["arm"],
                "profile": slot["profile"], **row,
            })
        rates = condition_rates(slot_rows)
        programs.append({
            "slot_id": slot["slot_id"], "task_id": slot["task_id"],
            "stratum": slot["stratum"], "arm": slot["arm"],
            "profile": slot["profile"], "interface_valid": valid, "rates": rates,
            "I_F": interaction(rates, "F"), "I_V": interaction(rates, "V"),
            "I_NE": interaction(rates, "NE"), "I_S0": interaction(rates, "S0"),
            "mechanism_positive": mechanism_positive(rates),
        })
    return rows, programs


def stage1() -> None:
    verify_freeze()
    tasks_list = read(HERE / "TASK_CATALOG.json")
    tasks = {task["task_id"]: task for task in tasks_list}
    indices = {task["task_id"]: index for index, task in enumerate(tasks_list)}
    slots = [slot for slot in read(HERE / "GENERATION_MANIFEST.json") if slot["stage"] == 1]
    if any(not (RUN / "generation" / slot["slot_id"] / "RESULT.json").exists() for slot in slots):
        raise RuntimeError("STAGE1_GENERATION_INCOMPLETE")
    rows, programs = evaluate_slots(slots, tasks, indices)
    positive = [program for program in programs if program["mechanism_positive"]]
    by_profile = {
        profile: sum(program["mechanism_positive"] for program in programs if program["profile"] == profile)
        for profile in ("deepseek_flash", "glm5")
    }
    positive_families = len({program["task_id"] for program in positive})
    gates = {
        "at_least_6_of_10_positive": len(positive) >= 6,
        "at_least_one_positive_each_profile": all(value >= 1 for value in by_profile.values()),
        "at_least_3_of_5_positive_families": positive_families >= 3,
    }
    result = {
        "schema": "paper3.rq2.coherent_pair_confirmation.stage1_gate.v1",
        "status": "CONTINUE" if all(gates.values()) else "STOP_FUTILITY",
        "stage1_programs": len(programs),
        "mechanism_positive_programs": len(positive),
        "positive_slot_ids": [program["slot_id"] for program in positive],
        "positive_by_profile": by_profile,
        "positive_families": positive_families,
        "gates": gates,
        "continue_remaining_86": all(gates.values()),
        "claim_boundary": "Sequential futility gate only; not a Paper3 result.",
    }
    write(RUN / "STAGE1_ROWS.json", rows)
    write(RUN / "STAGE1_PROGRAM_EFFECTS.json", programs)
    write(RUN / "STAGE1_GATE.json", result)
    print(json.dumps(result, indent=2))


def percentile(values: list[float], probability: float) -> float:
    return sorted(values)[int(probability * (len(values) - 1))]


def bootstrap_family_mean(families: list[dict], field: str, seed: int) -> list[float]:
    randomizer = random.Random(seed)
    draws = [
        sum(randomizer.choice(families)[field] for _ in families) / len(families)
        for _ in range(10000)
    ]
    return [percentile(draws, .025), percentile(draws, .975)]


def final() -> None:
    freeze = verify_freeze()
    if read(RUN / "STAGE1_GATE.json").get("continue_remaining_86") is not True:
        raise RuntimeError("STAGE1_STOPPED_STUDY")
    tasks_list = read(HERE / "TASK_CATALOG.json")
    tasks = {task["task_id"]: task for task in tasks_list}
    indices = {task["task_id"]: index for index, task in enumerate(tasks_list)}
    slots = read(HERE / "GENERATION_MANIFEST.json")
    if any(not (RUN / "generation" / slot["slot_id"] / "RESULT.json").exists() for slot in slots):
        raise RuntimeError("FULL_GENERATION_INCOMPLETE")
    rows, programs = evaluate_slots(slots, tasks, indices)

    by_key = {(program["task_id"], program["profile"], program["arm"]): program for program in programs}
    families = []
    for task in tasks_list:
        task_id = task["task_id"]
        base = [by_key[(task_id, profile, "BASE")] for profile in ("deepseek_flash", "glm5")]
        explicit = [by_key[(task_id, profile, "EXPLICIT")] for profile in ("deepseek_flash", "glm5")]
        families.append({
            "task_id": task_id, "stratum": task["stratum"],
            "base_I_F": sum(value["I_F"] for value in base) / 2,
            "base_I_V": sum(value["I_V"] for value in base) / 2,
            "base_I_NE": sum(value["I_NE"] for value in base) / 2,
            "explicit_I_F": sum(value["I_F"] for value in explicit) / 2,
            "D_F": sum(base[index]["I_F"] - explicit[index]["I_F"] for index in range(2)) / 2,
        })

    base_ci = bootstrap_family_mean(families, "base_I_F", 26091403)
    mitigation_ci = bootstrap_family_mean(families, "D_F", 26091404)
    base_programs = [program for program in programs if program["arm"] == "BASE"]
    explicit_programs = [program for program in programs if program["arm"] == "EXPLICIT"]
    base_profile_means = {
        profile: sum(program["I_F"] for program in base_programs if program["profile"] == profile) / 24
        for profile in ("deepseek_flash", "glm5")
    }
    mitigation_profile_means = {
        profile: sum(
            by_key[(task["task_id"], profile, "BASE")]["I_F"]
            - by_key[(task["task_id"], profile, "EXPLICIT")]["I_F"]
            for task in tasks_list
        ) / 24
        for profile in ("deepseek_flash", "glm5")
    }
    strata = sorted({family["stratum"] for family in families})
    stratum_means = {
        stratum: sum(family["base_I_F"] for family in families if family["stratum"] == stratum)
        / sum(family["stratum"] == stratum for family in families)
        for stratum in strata
    }
    contributions = {
        stratum: sum(max(0.0, family["base_I_F"]) for family in families if family["stratum"] == stratum)
        for stratum in strata
    }
    total_positive = sum(contributions.values())
    max_contribution = max(contributions.values()) / total_positive if total_positive else 1.0
    primary_gates = {
        "cluster_CI_lower_gt_zero": base_ci[0] > 0.0,
        "both_profiles_positive": all(value > 0.0 for value in base_profile_means.values()),
        "at_least_5_of_6_strata_positive": sum(value > 0.0 for value in stratum_means.values()) >= 5,
        "reference_and_oracle_gate_pass": read(RUN / "PRECALL_GATE.json").get("status") == "PASS",
        "no_stratum_over_half_positive_effect": max_contribution <= .5,
    }
    mitigation_gates = {
        "paired_cluster_CI_lower_gt_zero": mitigation_ci[0] > 0.0,
        "both_profiles_positive": all(value > 0.0 for value in mitigation_profile_means.values()),
    }
    result = {
        "schema": "paper3.rq2.coherent_pair_confirmation.final_machine_result.v1",
        "status": "MACHINE_STRONG_SUPPORT_HUMAN_REVIEW_PENDING" if all(primary_gates.values()) else "FINAL_GATE_FAIL_REPORT_BOUNDARY",
        "maximum_calls": freeze["maximum_first_response_calls"],
        "programs": len(programs), "families": len(families), "rows": len(rows),
        "base_mechanism_positive_programs": sum(program["mechanism_positive"] for program in base_programs),
        "explicit_mechanism_positive_programs": sum(program["mechanism_positive"] for program in explicit_programs),
        "primary_mean_base_I_F": sum(family["base_I_F"] for family in families) / len(families),
        "primary_cluster_bootstrap_95_CI": base_ci,
        "base_profile_mean_I_F": base_profile_means,
        "stratum_mean_base_I_F": stratum_means,
        "secondary_mean_base_I_V": sum(family["base_I_V"] for family in families) / len(families),
        "secondary_mean_base_I_NE": sum(family["base_I_NE"] for family in families) / len(families),
        "max_stratum_positive_contribution": max_contribution,
        "primary_gates": primary_gates,
        "mitigation_mean_D_F": sum(family["D_F"] for family in families) / len(families),
        "mitigation_cluster_bootstrap_95_CI": mitigation_ci,
        "mitigation_profile_mean_D_F": mitigation_profile_means,
        "mitigation_gates": mitigation_gates,
        "mitigation_supported": all(mitigation_gates.values()),
        "interface_valid_base": sum(program["interface_valid"] for program in base_programs),
        "interface_valid_explicit": sum(program["interface_valid"] for program in explicit_programs),
    }
    write(RUN / "FINAL_ROWS.json", rows)
    write(RUN / "FINAL_PROGRAM_EFFECTS.json", programs)
    write(RUN / "FINAL_FAMILY_EFFECTS.json", families)
    write(RUN / "FINAL_MACHINE_RESULT.json", result)
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["precall", "stage1", "final"])
    mode = parser.parse_args().mode
    {"precall": precall, "stage1": stage1, "final": final}[mode]()


if __name__ == "__main__":
    main()

