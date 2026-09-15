"""Create and execute the exact controlled mutation-family holdout; no model calls."""
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
from evaluate import evaluate


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def main():
    assert read(GATE)["status"] == "ACTIVE_HARD_GATE"
    q = read(P / "REFERENCE_QUALIFICATION.json")
    assert q["status"] == "PASS" and q["accepted"] == 64 and q["gate_sha256"] == sha(GATE)
    tasks = read(P / "TASK_CATALOG.json")
    targets = [x for x in tasks if x["family"] in ["D3_ATTR_FLAT", "D4_ATTR_NESTED"]]
    assert len(targets) == 8
    rows = []
    for target in targets:
        source = Path(target["reference_path"]).read_text()
        old = '''            if tool_owned:
                await robot.release_resource("LEFT", "tool")
'''
        new = '''            if tool_owned and i != 1:
                await robot.release_resource("LEFT", "tool")
'''
        assert source.count(old) == 1
        mutated = source.replace(old, new)
        spec = read(Path(target["spec_path"]))
        case_id = "MF-H1--" + target["task_id"]
        d = P / "mutation_holdout" / case_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "candidate.py").write_text(mutated)
        write(d / "SPEC.json", spec)
        capture = await execute(mutated, spec, R)
        if capture.get("process", {}).get("status") == "SANDBOX_SETUP_FAILED":
            raise RuntimeError(capture["process"].get("stderr"))
        geometry = evaluate_dynamic_evidence(spec, capture.get("trusted_events", []), None)
        evidence = evaluate(spec, capture, geometry, "P01")
        write(d / "CAPTURE.json", capture)
        write(d / "GEOMETRY.json", geometry)
        write(d / "EVIDENCE.json", evidence)
        terminal = evidence["summary"].get("TERMINAL")
        final_state = capture.get("trusted_events", [])[-1].get("scene_state", {}) if capture.get("trusted_events") else {}
        leak = final_state.get("resource_owners", {}).get("tool") == "LEFT"
        qualified = capture.get("execution_lifecycle_complete") and terminal == "V" and leak and geometry.get("status") == "NO_FORBIDDEN_CONTACT_IN_DECLARED_FIXED_AABB_TRANSLATIONS"
        rows.append({
            "case_id": case_id, "matched_reference_task_id": target["task_id"], "mutation_family": "MF-H1_SECOND_ITERATION_SECONDARY_RESOURCE_RELEASE_OMISSION",
            "source_sha256": sha(d / "candidate.py"), "matched_reference_source_sha256": target["reference_sha256"],
            "capture_sha256": sha(d / "CAPTURE.json"), "terminal_label": terminal, "observed_tool_owner_at_return": final_state.get("resource_owners", {}).get("tool"),
            "geometry_status": geometry.get("status"), "qualified": bool(qualified), "natural_data": False,
        })
        print(json.dumps({"case": case_id, "qualified": bool(qualified), "terminal": terminal, "tool_owner": final_state.get("resource_owners", {}).get("tool")}, ensure_ascii=False), flush=True)
    write(P / "MUTATION_HOLDOUT_QUALIFICATION.json", {"status": "PASS" if all(x["qualified"] for x in rows) else "FAIL", "family": "MF-H1_SECOND_ITERATION_SECONDARY_RESOURCE_RELEASE_OMISSION", "cases": 8, "rows": rows, "new_model_calls": 0, "natural_data": False, "matched_references": 8, "gate_sha256": sha(GATE)})
    if not all(x["qualified"] for x in rows):
        raise RuntimeError("Mutation holdout qualification failed")


if __name__ == "__main__":
    asyncio.run(main())
