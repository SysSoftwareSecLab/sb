"""Execute one natural program and preserve independent evidence."""
from pathlib import Path
import hashlib
import json
import sys

P = Path(__file__).resolve().parent
T = P.parent
Q = T.parent
R = Q.parents[1]
RUN = R / "05_formal/main_natural_384_v1"
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
from grammar_oracle import evaluate as grammar_evaluate


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unknown_rows(parent):
    return {"rows": [], "summary": {"EVIDENCE_AVAILABILITY": "U"}, "scope": "No parseable executable async entry; no candidate execution"}


async def measure(slot, task, generation_result):
    out = RUN / "evidence" / slot["slot_id"]
    done = out / "SUMMARY.json"
    if done.exists():
        saved = read(done)
        assert saved["generation_source_sha256"] == generation_result.get("source_sha256")
        return saved
    source_path = RUN / "generation" / slot["slot_id"] / "candidate.py"
    spec = read(Path(task["spec_path"]))
    if not generation_result.get("syntax_valid") or not generation_result.get("entry_present") or not source_path.exists():
        summary = {
            "slot_id": slot["slot_id"], "task_id": task["task_id"], "executed": False,
            "generation_source_sha256": generation_result.get("source_sha256"), "process_status": "NOT_EXECUTABLE_GENERATION",
            "task_evidence": unknown_rows(task["parent_evaluator"]), "grammar_evidence": {"rows": [], "summary": {"COMPOSITION": "U"}},
            "geometry_status": "U_NO_EXECUTABLE_TRACE", "execution_lifecycle_complete": False, "trusted_event_count": 0,
        }
        write(done, summary)
        return summary
    source = source_path.read_text()
    assert sha(source_path) == generation_result["source_sha256"]
    capture = await execute(source, spec, R)
    if capture.get("process", {}).get("status") == "SANDBOX_SETUP_FAILED":
        raise RuntimeError(capture["process"].get("stderr", "SANDBOX_SETUP_FAILED"))
    events = capture.get("trusted_events", [])
    geometry = evaluate_dynamic_evidence(spec, events, None) if events else {"status": "U_NO_TRUSTED_EVENTS"}
    parent = task["parent_evaluator"]
    if events:
        evaluator = batch_evaluate if parent.startswith("D") else parent_evaluate if parent.startswith("P") else structural_evaluate
        task_evidence = evaluator(spec, capture, geometry, parent)
    else:
        task_evidence = unknown_rows(parent)
    metrics = read(P / "REFERENCE_PAIR_METRICS.json")["metrics_by_task"][task["task_id"]]
    grammar = grammar_evaluate(task, spec, source, capture, metrics)
    write(out / "CAPTURE.json", capture)
    write(out / "GEOMETRY.json", geometry)
    write(out / "TASK_EVIDENCE.json", task_evidence)
    write(out / "GRAMMAR_EVIDENCE.json", grammar)
    task_labels = task_evidence.get("summary") or {x.get("obligation"): x.get("label") for x in task_evidence.get("rows", [])}
    summary = {
        "slot_id": slot["slot_id"], "task_id": task["task_id"], "executed": True,
        "generation_source_sha256": generation_result["source_sha256"], "process_status": capture.get("process", {}).get("status"),
        "execution_lifecycle_complete": bool(capture.get("execution_lifecycle_complete")), "trusted_event_count": len(events),
        "task_labels": task_labels, "grammar_labels": grammar.get("summary", {}), "geometry_status": geometry.get("status"),
        "capture_sha256": sha(out / "CAPTURE.json"), "task_evidence_sha256": sha(out / "TASK_EVIDENCE.json"),
        "grammar_evidence_sha256": sha(out / "GRAMMAR_EVIDENCE.json"), "geometry_sha256": sha(out / "GEOMETRY.json"),
        "whole_program_safety": None, "human_label": None,
    }
    write(done, summary)
    return summary

