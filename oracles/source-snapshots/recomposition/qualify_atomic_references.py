"""Verify the condition-blind A/B isolation fixtures on all 24 references."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QUALITY = HERE.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
from runtime import execute

from atomic_isolation import compose_atomic_isolation
from atomic_contract_oracle import dynamic_local_contract, static_local_contract


def read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def cleanup_ok(capture: dict, spec: dict) -> bool:
    events = capture.get("trusted_events", [])
    if not events:
        return False
    scene = events[-1].get("scene_state", {})
    return (
        scene.get("gripper_xyz_m", {}).get("LEFT") == spec["world"]["pose_coordinates_m"]["left_home"]
        and scene.get("gripper_xyz_m", {}).get("RIGHT") == spec["world"]["pose_coordinates_m"]["right_home"]
        and not scene.get("resource_owners", {})
        and not scene.get("active_events", {})
    )


async def main() -> None:
    catalog = read(HERE / "REFERENCE_TASK_CATALOG.json")
    rows = []
    for task in catalog:
        spec = read(HERE / task["spec_path"])
        source = (HERE / task["reference_source_path"]).read_text(encoding="utf-8")
        static_contract = static_local_contract(source, spec)
        for atom in ("A", "B"):
            capture = await execute(compose_atomic_isolation(source, spec, atom), spec, ROOT)
            dynamic_contract = dynamic_local_contract(capture, spec, atom)
            row = {
                "family_id": task["family_id"],
                "mechanism": task["mechanism"],
                "atom": atom,
                "lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
                "process_status": capture.get("process", {}).get("status"),
                "returncode": capture.get("process", {}).get("returncode"),
                "api_error_count": len(capture.get("trusted_api_errors", [])),
                "cleanup_ok": cleanup_ok(capture, spec),
                "static_contract_ok": static_contract["passed"],
                "static_contract_errors": static_contract["errors"],
                "dynamic_contract_ok": dynamic_contract["passed"],
                "dynamic_contract_reason": dynamic_contract["reason"],
            }
            row["passed"] = (
                row["lifecycle_complete"]
                and row["process_status"] == "EXITED"
                and row["returncode"] == 0
                and row["api_error_count"] == 0
                and row["cleanup_ok"]
                and row["static_contract_ok"]
                and row["dynamic_contract_ok"]
            )
            rows.append(row)
    failures = [row for row in rows if not row["passed"]]
    result = {
        "schema": "paper3.rq2.structure_preserving_recomposition.atomic_reference_qualification.v1",
        "status": "PASS" if not failures else "FAIL_BEFORE_MODEL_CALLS",
        "families": len(catalog),
        "atomic_executions": len(rows),
        "accepted_atomic_executions": len(rows) - len(failures),
        "failures": failures,
        "external_model_calls": 0,
        "rows": rows,
    }
    write_json(HERE / "ATOMIC_REFERENCE_QUALIFICATION.json", result)
    print(json.dumps({"status": result["status"], "accepted": result["accepted_atomic_executions"], "total": result["atomic_executions"], "failures": len(failures)}))


if __name__ == "__main__":
    asyncio.run(main())
