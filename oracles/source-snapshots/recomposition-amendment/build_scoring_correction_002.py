"""Version event-producer semantics without changing amendment-001 files."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
V4 = HERE.parent / "rq2_structure_preserving_recomposition_v4"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    original = read(HERE / "EVENT_SEMANTICS.json")
    corrected = []
    for row in original["families"]:
        item = copy.deepcopy(row)
        spec = read(V4 / "reference_tasks" / row["family_id"] / "SPEC.json")
        contract = spec["rq2_direct_p_contract"]
        for rule in item["persistent_active_states"]:
            if contract["oracle_kind"] in {"POSE_SUPPORT_DURING_ACTION", "CLEARANCE_BEFORE_ACTION"}:
                rule["producer_role"] = "A_EXTERNAL" if rule["event_id"] in contract.get("a_ready_events", []) else "B_SELF"
                rule["requires_matching_wait_version"] = rule["producer_role"] == "A_EXTERNAL"
            else:
                rule["producer_role"] = "A_EXTERNAL"
                rule["requires_matching_wait_version"] = True
        corrected.append(item)
    write_json(HERE / "EVENT_SEMANTICS_CORRECTION_002.json", {
        "schema": "paper3.rq2.v4_amendment.event_semantics.correction_002",
        "reason": "self-produced persistent events must be active at use but do not require the producer-consumer wait used for externally produced events",
        "families": corrected,
    })
    print(json.dumps({"families": len(corrected), "correction": "002"}, indent=2))


if __name__ == "__main__":
    main()
