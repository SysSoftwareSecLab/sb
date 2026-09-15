"""Create the immutable scientific input lock after all zero-call gates pass."""
from pathlib import Path
import datetime
import hashlib
import json

P = Path(__file__).resolve().parent
R = P.parents[3]
GATE = R / "01_project/MAINLINE_ADMISSION_2026-09-12.json"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert read(GATE)["status"] == "ACTIVE_HARD_GATE"
    assert read(P / "DESIGN_VALIDATION.json")["status"] == "PASS_READY_TO_FREEZE"
    assert read(P / "REFERENCE_QUALIFICATION.json")["status"] == "PASS"
    assert read(P / "MUTATION_HOLDOUT_QUALIFICATION.json")["status"] == "PASS"
    fixed = [
        GATE, P / "PROTOCOL.md", P / "TASK_GRAMMAR.json", P / "TASK_CATALOG.json", P / "STRUCTURAL_PAIRS.json",
        P / "REACHABLE_EXPOSURE_LEDGER.json", P / "HOLDOUT_REGISTRY.json", P / "MODEL_PROFILES.json",
        P / "GENERATION_MANIFEST.json", P / "MAIN_TABLE_BINDING.json", P / "WORKLOAD_AND_STOP.json",
        P / "REFERENCE_QUALIFICATION.json", P / "REFERENCE_PAIR_METRICS.json", P / "DESIGN_VALIDATION.json",
        P / "CAPABILITY_ITEMS_PUBLIC.json", P / "CAPABILITY_GOLD_PRIVATE.json", P / "CAPABILITY_MANIFEST.json", P / "CAPABILITY_STATUS.json",
        P / "MUTATION_HOLDOUT_QUALIFICATION.json", P / "grammar_oracle.py", P / "measure_natural.py", P / "run_collection.py",
        P / "package_human.py", P / "deliver_to_mac.py", P.parent / "formal_replacement_v2/collect.py", P.parent / "formal_replacement_v2/PUBLIC_API.md",
    ]
    fixed += sorted(x for x in (P / "tasks").rglob("*") if x.is_file())
    fixed += sorted(x for x in (P / "mutation_holdout").rglob("*") if x.is_file())
    assert len(fixed) == len(set(fixed)) and all(x.exists() for x in fixed)
    files = [{"path": str(x.relative_to(R)), "sha256": sha(x), "bytes": x.stat().st_size} for x in fixed]
    freeze = {
        "status": "FROZEN_FOR_MAIN_COLLECTION", "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "gate_sha256": sha(GATE), "files": files, "file_count": len(files),
        "natural_slots": 384, "capability_slots": 192, "controlled_mutation_cases": 8,
        "result_root": str(R / "05_formal/main_natural_384_v1"),
        "transport_policy": "one received body per frozen slot; retry transport only; never quality-resample",
        "human_policy": "one combined blind package, two reviewers, no machine labels or model identities",
        "other_research_directories": "READ_ONLY",
        "result_independent_stop": "stop after all frozen slots and one double-human review; zero or negative findings do not trigger replacement probes",
    }
    (P / "SCIENTIFIC_FREEZE.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": freeze["status"], "files": len(files), "natural": 384, "capability": 192, "mutation": 8, "gate_sha256": freeze["gate_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
