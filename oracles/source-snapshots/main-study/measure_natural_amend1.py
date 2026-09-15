"""Technical-amendment measurement adapter; scientific rules are unchanged.

The legacy S04/S05 evaluator assumed every proposed signal event id began with
lower-case ``left`` or ``right`` and raised KeyError on malformed natural model
output.  A malformed event id is evidence against the protocol, not a reason to
abort collection.  This adapter makes that legacy evaluator total while keeping
the original capture unchanged on disk.
"""
from copy import deepcopy

import measure_natural as base


def structural_evaluate_total(spec, capture, geometry, parent):
    adapted = deepcopy(capture)
    adapted_count = 0
    for call in adapted.get("call_audit", []):
        if call.get("action") != "signal":
            continue
        parameters = call.get("parameters") or {}
        event_id = parameters.get("event_id")
        if event_id in {"left_ready", "right_ready"}:
            continue
        arm = parameters.get("arm")
        # Give the legacy checker a structurally valid key, while forcing its
        # item binding test to fail.  This maps malformed/unknown ready events
        # to protocol V instead of silently normalising their actual identity.
        parameters["event_id"] = "left_ready" if arm == "LEFT" else "right_ready"
        parameters["item_id"] = "__INVALID_EVENT_ID__"
        call["parameters"] = parameters
        adapted_count += 1
    evidence = base.structural_evaluate(spec, adapted, geometry, parent)
    evidence["technical_adapter"] = {
        "id": "TECHNICAL_AMENDMENT_001",
        "malformed_signal_calls_mapped_to_protocol_violation": adapted_count,
        "stored_capture_modified": False,
        "scientific_rule_changed": False,
    }
    return evidence


async def measure(slot, task, generation_result):
    out = base.RUN / "evidence" / slot["slot_id"]
    done = out / "SUMMARY.json"
    if done.exists():
        saved = base.read(done)
        assert saved["generation_source_sha256"] == generation_result.get("source_sha256")
        return saved
    source_path = base.RUN / "generation" / slot["slot_id"] / "candidate.py"
    spec = base.read(base.Path(task["spec_path"]))
    if not generation_result.get("syntax_valid") or not generation_result.get("entry_present") or not source_path.exists():
        summary = {
            "slot_id": slot["slot_id"], "task_id": task["task_id"], "executed": False,
            "generation_source_sha256": generation_result.get("source_sha256"), "process_status": "NOT_EXECUTABLE_GENERATION",
            "task_evidence": base.unknown_rows(task["parent_evaluator"]), "grammar_evidence": {"rows": [], "summary": {"COMPOSITION": "U"}},
            "geometry_status": "U_NO_EXECUTABLE_TRACE", "execution_lifecycle_complete": False, "trusted_event_count": 0,
        }
        base.write(done, summary)
        return summary
    source = source_path.read_text()
    assert base.sha(source_path) == generation_result["source_sha256"]
    capture = await base.execute(source, spec, base.R)
    if capture.get("process", {}).get("status") == "SANDBOX_SETUP_FAILED":
        raise RuntimeError(capture["process"].get("stderr", "SANDBOX_SETUP_FAILED"))
    events = capture.get("trusted_events", [])
    geometry = base.evaluate_dynamic_evidence(spec, events, None) if events else {"status": "U_NO_TRUSTED_EVENTS"}

    # Preserve the exact capture before any evaluator runs.  This is execution
    # durability only and does not alter the candidate or any scientific rule.
    base.write(out / "CAPTURE.json", capture)
    base.write(out / "GEOMETRY.json", geometry)

    parent = task["parent_evaluator"]
    if events:
        evaluator = base.batch_evaluate if parent.startswith("D") else base.parent_evaluate if parent.startswith("P") else structural_evaluate_total
        task_evidence = evaluator(spec, capture, geometry, parent)
    else:
        task_evidence = base.unknown_rows(parent)
    metrics = base.read(base.P / "REFERENCE_PAIR_METRICS.json")["metrics_by_task"][task["task_id"]]
    grammar = base.grammar_evaluate(task, spec, source, capture, metrics)
    base.write(out / "TASK_EVIDENCE.json", task_evidence)
    base.write(out / "GRAMMAR_EVIDENCE.json", grammar)
    task_labels = task_evidence.get("summary") or {x.get("obligation"): x.get("label") for x in task_evidence.get("rows", [])}
    summary = {
        "slot_id": slot["slot_id"], "task_id": task["task_id"], "executed": True,
        "generation_source_sha256": generation_result["source_sha256"], "process_status": capture.get("process", {}).get("status"),
        "execution_lifecycle_complete": bool(capture.get("execution_lifecycle_complete")), "trusted_event_count": len(events),
        "task_labels": task_labels, "grammar_labels": grammar.get("summary", {}), "geometry_status": geometry.get("status"),
        "capture_sha256": base.sha(out / "CAPTURE.json"), "task_evidence_sha256": base.sha(out / "TASK_EVIDENCE.json"),
        "grammar_evidence_sha256": base.sha(out / "GRAMMAR_EVIDENCE.json"), "geometry_sha256": base.sha(out / "GEOMETRY.json"),
        "whole_program_safety": None, "human_label": None, "technical_amendment": "TECHNICAL_AMENDMENT_001",
    }
    base.write(done, summary)
    return summary
