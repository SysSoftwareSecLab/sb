"""Execute and assess the versioned MC04 post-release-departure repair.

These are new, self-authored calibration fixtures.  They do not replace or
rerun the retained D references, whose post-release violations remain evidence.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from bisafebench_pilot.forward_calibration_v01.forward_controller_v01_candidate import (
    execute_forward_isolated,
)
from bisafebench_pilot.forward_calibration_v01.run_references_v01 import replay_forward

from geometry_interface_v01 import evaluate_dynamic_evidence


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_sha256(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def bind(path, role):
    path = Path(path).resolve()
    return {"role": role, "path": str(path), "sha256": sha256(path)}


async def run(args):
    project = Path(args.project_root).resolve()
    amendment_dir = Path(args.amendment_dir).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    ready_path = amendment_dir / "AMENDMENT_READY.json"
    ready = json.loads(ready_path.read_text())
    if sha256(ready_path) != "3c0bdb9b1278f74545ef4fcaf69104ce01959a794e1f69ec0b697cadb22a29e4":
        raise RuntimeError("Unexpected MC04 repair release hash")

    local_sources = [
        Path(__file__),
        Path(__file__).with_name("geometry_interface_v01.py"),
        Path(__file__).with_name("dynamic_geometry_v01.py"),
    ]
    shared_sources = [
        project / "src/bisafebench_pilot/sandbox_clock_v05.py",
        project / "src/bisafebench_pilot/sandbox_clock_v04.py",
        project / "src/bisafebench_pilot/sandbox_client_clock_v04.py",
        project / "src/bisafebench_pilot/sandbox_controller_v03.py",
        project / "src/bisafebench_pilot/sandbox_process_v03.py",
        project / "src/bisafebench_pilot/sandbox_worker_v03.py",
        project / "src/bisafebench_pilot/forward_calibration_v01/forward_runtime_v01_candidate.py",
        project / "src/bisafebench_pilot/forward_calibration_v01/forward_controller_v01_candidate.py",
        project / "src/bisafebench_pilot/forward_calibration_v01/client_extension_v01_candidate.py",
        project / "src/bisafebench_pilot/forward_calibration_v01/timeout_semantics_v01_candidate.py",
        project / "src/bisafebench_pilot/forward_calibration_v01/evidence_pipeline_v03_candidate.py",
        project / "src/bisafebench_pilot/forward_calibration_v01/run_references_v01.py",
    ]
    amendment_files = [ready_path]
    for row in ready["bindings"]:
        amendment_files.extend((Path(row["effective_spec"]), Path(row["reference"])))
    lock = {
        "schema_version": 1,
        "release_id": "P3-G-MC04-REPAIR-PRE-RUN-LOCK-0.1.0",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": "LOCKED_BEFORE_FIRST_CANDIDATE_EXECUTION",
        "files": ([bind(path, "G_EXECUTION_OR_EVALUATION_SOURCE") for path in local_sources]
                  + [bind(path, "SHARED_V05_RUNTIME_SOURCE") for path in shared_sources]
                  + [bind(path, "MAIN_VERSIONED_AMENDMENT_INPUT") for path in amendment_files]),
        "old_retained_references_executed": 0,
        "new_self_authored_candidate_programs_planned": 2,
        "model_calls": 0,
        "human_labels_created": 0,
        "hardware_operations": 0,
    }
    lock_path = output / "PRE_RUN_LOCK.json"
    lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")

    rows = []
    for binding in ready["bindings"]:
        spec_path = Path(binding["effective_spec"])
        source_path = Path(binding["reference"])
        if sha256(spec_path) != binding["effective_spec_sha256"]:
            raise RuntimeError("Repair effective-spec hash mismatch")
        if sha256(source_path) != binding["reference_sha256"]:
            raise RuntimeError("Repair reference hash mismatch")
        spec = json.loads(spec_path.read_text())
        result = await execute_forward_isolated(
            source_path.read_text(), spec, project_root=project, event_replay=replay_forward
        )
        dynamic = evaluate_dynamic_evidence(
            spec, result["trusted_events"], result["independent_replay"]
        )
        trace = {
            "schema_version": 1,
            "release_id": "P3-G-MC04-REPAIR-EXECUTION-0.1.0",
            "task_id": spec["task_id"],
            "variant": spec["variant"],
            "source": bind(source_path, "SELF_AUTHORED_REPAIR_REFERENCE"),
            "spec": bind(spec_path, "MAIN_AUTHORIZED_FORWARD_EFFECTIVE_SPEC"),
            "process": result["process"],
            "event_source": result["event_source"],
            "clock_protocol": result["clock_protocol"],
            "logical": result["independent_replay"],
            "trusted_events": result["trusted_events"],
            "dynamic_geometry": dynamic,
            "safety_label": None,
        }
        trace_path = output / f"{spec['task_id']}_REPAIR_TRACE.json"
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
        process_ok = (result["process"].get("status") == "EXITED"
                      and result["process"].get("returncode") == 0)
        geometry_ok = (
            dynamic["status"] == "NO_FORBIDDEN_CONTACT_IN_DECLARED_FIXED_AABB_TRANSLATIONS"
            and dynamic["pair_coverage"]["status"] == "PASS"
            and dynamic["reconstruction_checks"]["status"] == "PASS"
            and dynamic["bullet_consistency"]["status"] == "PASS"
        )
        rows.append({
            "task_id": spec["task_id"],
            "variant": spec["variant"],
            "status": "PASS" if process_ok and result["independent_replay"]["status"] == "PASS" and geometry_ok else "FAIL",
            "process_status": result["process"].get("status"),
            "process_returncode": result["process"].get("returncode"),
            "logical_status": result["independent_replay"]["status"],
            "dynamic_status": dynamic["status"],
            "pair_coverage_status": dynamic["pair_coverage"]["status"],
            "reconstruction_status": dynamic["reconstruction_checks"]["status"],
            "bullet_status": dynamic["bullet_consistency"]["status"],
            "bullet_query_count": dynamic["bullet_consistency"]["query_count"],
            "finding_count": len(dynamic["findings"]),
            "post_release_permission": [record for record in dynamic["permission_windows"]
                                         if record["kind"] == "POST_RELEASE_DEPARTURE"],
            "trace": {"path": str(trace_path), "sha256": sha256(trace_path)},
        })

    report = {
        "schema_version": 1,
        "release_id": "P3-G-MC04-REPAIR-VALIDATION-0.1.0",
        "status": "PASS" if len(rows) == 2 and all(row["status"] == "PASS" for row in rows) else "FAIL",
        "amendment_ready": bind(ready_path, "MAIN_AUTHORIZED_FORWARD_AMENDMENT"),
        "pre_run_lock": {"path": str(lock_path), "sha256": sha256(lock_path)},
        "candidate_program_count": 2,
        "pass_count": sum(row["status"] == "PASS" for row in rows),
        "results": rows,
        "old_retained_reference_results_overwritten": False,
        "old_retained_references_executed": 0,
        "interpretation": "This validates only the versioned forward repair candidate. The two original retained MC04 violation traces remain unchanged and remain positive evidence.",
        "model_calls": 0,
        "baseline_calls": 0,
        "human_labels_created": 0,
        "natural_programs": 0,
        "controlled_mutations": 0,
        "self_authored_tool_fixtures": 2,
        "hardware_operations": 0,
        "safety_label": None,
    }
    report_path = output / "MC04_REPAIR_VALIDATION.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "pass_count": report["pass_count"]}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--amendment-dir", required=True)
    parser.add_argument("--output", required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
