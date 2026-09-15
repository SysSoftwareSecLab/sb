"""Execute and qualify all frozen-design reference witnesses; no model calls."""
from pathlib import Path
import asyncio
import hashlib
import json
import sys

P = Path(__file__).resolve().parent
T = P.parent
Q = T.parent
R = Q.parents[1]
GATE = R / "01_project/MAINLINE_ADMISSION_2026-09-12.json"
sys.path.insert(0, str(Q / "trace_dev_v1"))
from runtime import execute
sys.path.insert(0, str(R / "01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src"))
from geometry_interface_v01 import evaluate_dynamic_evidence
sys.path.insert(0, str(Q / "task2_evidence"))
from evaluate import evaluate as parent_evaluate
sys.path.insert(0, str(T / "structural_batch"))
from measure import evaluate as structural_evaluate
sys.path.insert(0, str(Q / "batch_7_9"))
from evidence import evaluate as batch_evaluate


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_design():
    status = read(P / "PREPARE_STATUS.json")
    assert status["status"] == "COMPILED_AWAITING_REFERENCE_QUALIFICATION"
    assert status["gate_sha256"] == sha(GATE), "Mainline admission gate changed"
    assert read(GATE)["status"] == "ACTIVE_HARD_GATE"
    tasks = read(P / "TASK_CATALOG.json")
    assert len(tasks) == 64
    for row in tasks:
        assert sha(Path(row["spec_path"])) == row["spec_sha256"]
        assert sha(Path(row["reference_path"])) == row["reference_sha256"]
        assert sha(Path(row["graph_path"])) == row["graph_sha256"]
    return tasks


async def main():
    tasks = verify_design()
    rows = []
    for n, row in enumerate(tasks, 1):
        d = Path(row["spec_path"]).parent
        spec = read(d / "SPEC.json")
        source = (d / "reference.py").read_text()
        capture = await execute(source, spec, R)
        if capture.get("process", {}).get("status") == "SANDBOX_SETUP_FAILED":
            raise RuntimeError(capture["process"].get("stderr", "SANDBOX_SETUP_FAILED"))
        geometry = evaluate_dynamic_evidence(spec, capture.get("trusted_events", []), None)
        parent = row["parent_evaluator"]
        evaluator = batch_evaluate if parent.startswith("D") else parent_evaluate if parent.startswith("P") else structural_evaluate
        evidence = evaluator(spec, capture, geometry, parent)
        write(d / "CAPTURE.json", capture)
        write(d / "GEOMETRY.json", geometry)
        write(d / "EVIDENCE.json", evidence)
        labels = evidence.get("summary") or {x["obligation"]: x["label"] for x in evidence.get("rows", [])}
        geometry_ok = geometry.get("status") in ["NO_FORBIDDEN_CONTACT_IN_DECLARED_FIXED_AABB_TRANSLATIONS", "NOT_APPLICABLE"]
        accepted = bool(capture.get("execution_lifecycle_complete")) and geometry_ok and all(v in ["C", "NA"] for v in labels.values())
        result = {
            "task_id": row["task_id"], "reference_accepted": accepted,
            "execution_lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
            "process_status": capture.get("process", {}).get("status"), "geometry_status": geometry.get("status"),
            "labels": labels, "trusted_event_count": len(capture.get("trusted_events", [])),
            "capture_sha256": sha(d / "CAPTURE.json"), "geometry_sha256": sha(d / "GEOMETRY.json"), "evidence_sha256": sha(d / "EVIDENCE.json"),
        }
        rows.append(result)
        print(json.dumps({"n": n, "task": row["task_id"], "accepted": accepted, "process": result["process_status"], "geometry": result["geometry_status"]}, ensure_ascii=False), flush=True)
    failed = [x["task_id"] for x in rows if not x["reference_accepted"]]
    write(P / "REFERENCE_QUALIFICATION.json", {"status": "PASS" if not failed else "FAIL_MAIN_DESIGN_REVISION_REQUIRED", "rows": rows, "accepted": len(rows) - len(failed), "failed": failed, "new_model_calls": 0, "new_reference_executions": len(rows), "gate_sha256": sha(GATE)})
    if failed:
        raise RuntimeError("Reference gate failed: " + ",".join(failed))


if __name__ == "__main__":
    asyncio.run(main())
