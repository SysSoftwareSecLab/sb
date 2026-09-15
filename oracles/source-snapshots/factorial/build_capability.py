"""Freeze a four-dimensional capability instrument before capability calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


P = Path(__file__).resolve().parent
ROOT = P.parents[3]
BASE = P.parent / "main_study_v1"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    if (P / "CAPABILITY_FREEZE.json").exists():
        raise RuntimeError("Capability instrument already frozen")
    main_freeze = read(P / "SCIENTIFIC_FREEZE.json")
    assert main_freeze["status"] == "FROZEN_READY_FOR_CAPABILITY_AND_NATURAL_COLLECTION"
    profiles = {row["id"]: row for row in read(P / "MODEL_PROFILES.json")}
    profile_ids = ["glm46", "glm47", "glm5", "glm52"]

    public_items = []
    gold = {}
    for item in read(BASE / "CAPABILITY_ITEMS_PUBLIC.json"):
        domain = "async_timing" if item["domain"] == "async_schedule" else item["domain"]
        public_items.append({"item_id": item["item_id"], "domain": domain, "format": "EXACT_JSON", "prompt": item["prompt"]})
        gold[item["item_id"]] = read(BASE / "CAPABILITY_GOLD_PRIVATE.json")[item["item_id"]]

    mutation = read(BASE / "MUTATION_HOLDOUT_QUALIFICATION.json")
    assert mutation["status"] == "PASS" and all(row["qualified"] for row in mutation["rows"])
    base_catalog = {row["task_id"]: row for row in read(BASE / "TASK_CATALOG.json")}
    for row in mutation["rows"]:
        case_dir = BASE / "mutation_holdout" / row["case_id"]
        spec = read(case_dir / "SPEC.json")
        # Experimental assignments and holdout names are irrelevant to the
        # discrimination item and are omitted from the model-visible task.
        visible_spec = {
            key: value for key, value in spec.items()
            if key not in {"experimental_assignment", "development_contract"}
        }
        correct_source = Path(base_catalog[row["matched_reference_task_id"]]["reference_path"]).read_text(encoding="utf-8")
        mutated_source = (case_dir / "candidate.py").read_text(encoding="utf-8")
        for order in ["CORRECT_FIRST", "CORRECT_SECOND"]:
            item_id = f"CAP-LONG-{row['case_id']}-{'A' if order == 'CORRECT_FIRST' else 'B'}"
            candidates = [correct_source, mutated_source] if order == "CORRECT_FIRST" else [mutated_source, correct_source]
            prompt = (
                "Given the public robot task and two complete candidate programs, choose the one that satisfies the task and finite robot contract. "
                "Return only A or B as requested.\nPUBLIC TASK\n"
                + json.dumps(visible_spec, ensure_ascii=False, sort_keys=True)
                + "\nCANDIDATE A\n" + candidates[0]
                + "\nCANDIDATE B\n" + candidates[1]
            )
            public_items.append({
                "item_id": item_id, "domain": "long_context_program_discrimination", "format": "EXACT_JSON",
                "prompt": prompt, "qualification_case": row["case_id"],
                "candidate_a_sha256": hashlib.sha256(candidates[0].encode()).hexdigest(),
                "candidate_b_sha256": hashlib.sha256(candidates[1].encode()).hexdigest(),
            })
            gold[item_id] = "A" if order == "CORRECT_FIRST" else "B"

    assert len(public_items) == 64
    assert {item["domain"] for item in public_items} == {
        "task_graph", "state_and_identity", "async_timing", "long_context_program_discrimination"
    }
    assert all(sum(item["domain"] == domain for item in public_items) == 16 for domain in {
        "task_graph", "state_and_identity", "async_timing", "long_context_program_discrimination"
    })

    manifest = []
    for item in public_items:
        for profile_id in profile_ids:
            profile = profiles[profile_id]
            payload = {
                "model": profile["model"], "thinking": {"type": "disabled"}, "temperature": 0.0,
                "max_tokens": 128, "stream": False,
                "messages": [
                    {"role": "system", "content": "Solve the deterministic item. Return exactly one JSON object {\"answer\":\"...\"}; no Markdown, explanation, or extra keys."},
                    {"role": "user", "content": item["prompt"]},
                ],
            }
            manifest.append({
                "slot_id": f"{item['item_id']}--{profile_id}", "item_id": item["item_id"],
                "domain": item["domain"], "profile": profile_id, "request": payload,
                "request_sha256": request_hash(payload),
            })
    manifest.sort(key=lambda row: hashlib.sha256(("rq4-multidimensional-capability-v1/" + row["slot_id"]).encode()).hexdigest())
    assert len(manifest) == 256 and len({row["slot_id"] for row in manifest}) == 256
    serialized_requests = json.dumps([row["request"] for row in manifest], ensure_ascii=False)
    assert not any(answer in serialized_requests for answer in ["CAPABILITY_GOLD_PRIVATE"])

    write(P / "CAPABILITY_ITEMS_PUBLIC_V2.json", public_items)
    write(P / "CAPABILITY_GOLD_PRIVATE_V2.json", gold)
    write(P / "CAPABILITY_MANIFEST_V2.json", manifest)
    write(P / "CAPABILITY_ANALYSIS_PLAN.json", {
        "status": "FROZEN_BEFORE_CAPABILITY_CALLS",
        "profiles_in_version_order": profile_ids,
        "dimensions": ["task_graph", "state_and_identity", "async_timing", "long_context_program_discrimination"],
        "items_per_dimension_per_profile": 16,
        "scalar_total_or_rank_forbidden": True,
        "adjacent_pair_gate": "For an endpoint, every mapped dimension must be nondecreasing and at least one strictly higher; otherwise report version association only.",
        "endpoint_dimension_map": {
            "S0_S1": ["task_graph", "long_context_program_discrimination"],
            "S2": ["state_and_identity"],
            "P": ["async_timing", "state_and_identity"],
            "O": ["state_and_identity"],
        },
        "long_context_scope": "One independently qualified resource-lifecycle mutation family over eight task cases; supports only the stated discrimination dimension.",
        "no_human_labels": True,
    })
    files = [
        P / "SCIENTIFIC_FREEZE.json", P / "build_capability.py", P / "run_capability.py", P / "CAPABILITY_ITEMS_PUBLIC_V2.json",
        P / "CAPABILITY_GOLD_PRIVATE_V2.json", P / "CAPABILITY_MANIFEST_V2.json", P / "CAPABILITY_ANALYSIS_PLAN.json",
    ]
    write(P / "CAPABILITY_FREEZE.json", {
        "status": "FROZEN_BEFORE_CAPABILITY_CALLS", "scientific_calls_before_freeze": 0,
        "items": 64, "profiles": 4, "calls": 256, "scalar_capability_order_forbidden": True,
        "files": [{"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size} for path in sorted(files)],
    })
    print(json.dumps({"status": "CAPABILITY_FROZEN", "items": 64, "profiles": 4, "calls": 256}, ensure_ascii=False))


if __name__ == "__main__":
    main()
