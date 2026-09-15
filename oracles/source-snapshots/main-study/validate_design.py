"""Validate pair construction, holdouts and request denominators before freeze."""
from pathlib import Path
from collections import Counter
import hashlib
import json

from grammar_oracle import action_multiset, cross_arm_overlap, focal_distance, evaluate

P = Path(__file__).resolve().parent
R = P.parents[3]
GATE = R / "01_project/MAINLINE_ADMISSION_2026-09-12.json"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    gate_hash = sha(GATE)
    assert read(GATE)["status"] == "ACTIVE_HARD_GATE"
    reference = read(P / "REFERENCE_QUALIFICATION.json")
    mutation = read(P / "MUTATION_HOLDOUT_QUALIFICATION.json")
    exposure = read(P / "REACHABLE_EXPOSURE_LEDGER.json")
    assert reference["status"] == "PASS" and reference["accepted"] == 64 and reference["gate_sha256"] == gate_hash
    assert mutation["status"] == "PASS" and mutation["cases"] == 8 and mutation["gate_sha256"] == gate_hash
    assert all(v is True for k, v in exposure["holdout_checks"].items() if isinstance(v, bool))
    tasks = read(P / "TASK_CATALOG.json")
    pairs = read(P / "STRUCTURAL_PAIRS.json")
    task_by_id = {x["task_id"]: x for x in tasks}
    assert len(tasks) == 64 and len(pairs) == 32
    captures = {x["task_id"]: read(Path(x["spec_path"]).parent / "CAPTURE.json") for x in tasks}
    pair_rows, metrics_by_task = [], {}
    for pair in pairs:
        members = [task_by_id[x] for x in pair["members"]]
        assert len(members) == 2
        counts = [action_multiset(captures[x["task_id"]]) for x in members]
        multiset_equal = counts[0] == counts[1]
        if pair["axis"] == "CONCURRENCY":
            serial = next(x for x in members if x["level"] == "SERIAL")
            concurrent = next(x for x in members if x["level"] == "CONCURRENT")
            lo = cross_arm_overlap(captures[serial["task_id"]])
            hi = cross_arm_overlap(captures[concurrent["task_id"]])
            contrast_ok = hi > lo
            metric = {"serial_overlap": lo, "concurrent_overlap": hi}
        else:
            short = next(x for x in members if x["level"] == "SHORT")
            long = next(x for x in members if x["level"] == "LONG")
            lo = focal_distance(short, captures[short["task_id"]])
            hi = focal_distance(long, captures[long["task_id"]])
            contrast_ok = hi > lo
            metric = {"short_distance": lo, "long_distance": hi}
        for x in members:
            metrics_by_task[x["task_id"]] = metric
        pair_rows.append({"pair_id": pair["pair_id"], "axis": pair["axis"], "action_multiset_equal": multiset_equal, "contrast_realized": contrast_ok, **metric, "members": pair["members"]})
    assert all(x["action_multiset_equal"] and x["contrast_realized"] for x in pair_rows)

    # L0/LH differ in public topology while retaining byte-identical source.
    layout_rows = []
    for family in sorted({x["family"] for x in tasks}):
        for level in sorted({x["level"] for x in tasks if x["family"] == family}):
            l0 = next(x for x in tasks if x["family"] == family and x["level"] == level and x["layout"] == "L0")
            lh = next(x for x in tasks if x["family"] == family and x["level"] == level and x["layout"] == "LH")
            layout_rows.append({"family": family, "level": level, "same_source": l0["reference_sha256"] == lh["reference_sha256"], "different_spec": l0["spec_sha256"] != lh["spec_sha256"]})
    assert all(x["same_source"] and x["different_spec"] for x in layout_rows)

    oracle_rows = []
    for task in tasks:
        d = Path(task["spec_path"]).parent
        result = evaluate(task, read(d / "SPEC.json"), (d / "reference.py").read_text(), captures[task["task_id"]], metrics_by_task[task["task_id"]])
        labels = result["summary"]
        oracle_rows.append({"task_id": task["task_id"], "labels": labels, "accepted": all(x in ["C", "NA"] for x in labels.values())})
    assert all(x["accepted"] for x in oracle_rows)

    slots = read(P / "GENERATION_MANIFEST.json")
    capability = read(P / "CAPABILITY_MANIFEST.json")
    assert len(slots) == 384 and len({x["slot_id"] for x in slots}) == 384
    assert len(capability) == 192 and len({x["slot_id"] for x in capability}) == 192
    assert Counter(x["profile"] for x in slots) == {"deepseek_flash": 128, "glm47": 128, "glm5": 128}
    assert Counter(x["axis"] for x in slots) == {"CONCURRENCY": 192, "DEPENDENCY_DISTANCE": 192}
    assert Counter(x["profile"] for x in capability) == {"glm47": 96, "glm5": 96}
    forbidden = ["[LOCAL_PATH_REMOVED]", "reviewer_name", "expected_findings", "CAPABILITY_GOLD_PRIVATE", "human_label"]
    assert all(not any(term in json.dumps(x["request"], ensure_ascii=False) for term in forbidden) for x in slots + capability)
    write(P / "REFERENCE_PAIR_METRICS.json", {"pairs": pair_rows, "metrics_by_task": metrics_by_task})
    write(P / "DESIGN_VALIDATION.json", {
        "status": "PASS_READY_TO_FREEZE", "gate_sha256": gate_hash,
        "reference_tasks": 64, "reference_accepted": 64, "structural_pairs": 32, "pair_action_multiset_equal": 32, "pair_contrast_realized": 32,
        "layout_pairs": 32, "layout_source_held_constant": 32, "grammar_oracle_reference_pass": 64,
        "holdout_types": 4, "mutation_cases": 8, "natural_slots": 384, "capability_slots": 192,
        "natural_profile_counts": dict(Counter(x["profile"] for x in slots)), "natural_axis_counts": dict(Counter(x["axis"] for x in slots)),
        "request_leakage_check": "PASS", "new_model_calls": 0, "main_design_revision_count": 1,
        "old_data_basis": {"programs": 360, "any_U_programs": 138, "violation_lower": 92, "parent_ICC_lower": 0.11693312780674564, "parent_ICC_upper": 0.48108313712360673},
        "resource_decision": "Hold total natural N at 384 but allocate to 16 families and one generation per cell, not 8 families and two within-cell repeats.",
    })
    print(json.dumps({"status": "PASS_READY_TO_FREEZE", "tasks": 64, "pairs": 32, "natural": 384, "capability": 192, "mutations": 8}, ensure_ascii=False))


if __name__ == "__main__":
    main()
