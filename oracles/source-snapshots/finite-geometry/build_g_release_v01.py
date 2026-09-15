"""Build hash-bound Stage 3 G coverage, validation, and handoff manifests."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path, role=None):
    path = Path(path).resolve()
    row = {"path": str(path), "sha256": sha256(path)}
    if role is not None:
        row["role"] = role
    return row


def load_bound(path, expected=None):
    path = Path(path).resolve()
    actual = sha256(path)
    if expected is not None and actual != expected:
        raise RuntimeError(f"Hash mismatch for {path}: {actual} != {expected}")
    return json.loads(path.read_text())


def detailed_coverage(compact):
    full_path = Path(compact["full_result"]["path"])
    full = load_bound(full_path, compact["full_result"]["sha256"])
    segments = [
        {"segment_id": row["segment_id"], "time_interval_s": row["time_interval_s"],
         "moving_bodies": row["moving_bodies"]}
        for row in full["motion_segments"]
    ]
    points = sorted({value for row in segments for value in row["time_interval_s"]})
    pairs = []
    for pair_row in full["pair_coverage"]["pairs"]:
        pair = pair_row["pair"]
        pairs.append({
            **pair_row,
            "evaluated_time_intervals": [row["time_interval_s"] for row in segments],
            "evaluated_event_or_boundary_times_s": points,
            "contact_windows": [row for row in full["contact_windows"] if row["pair"] == pair],
            "findings": [row for row in full["findings"] if row["pair"] == pair],
        })
    return {
        "task_id": full["task_id"], "axis_id": full["axis_id"], "variant": full["variant"],
        "status": full["status"], "trace_complete": full["trace_complete"],
        "modeled_solids": full["pair_coverage"]["inventory"]["modeled_solids"],
        "time_segments": segments, "event_or_boundary_times_s": points,
        "pairs": pairs, "pair_coverage_status": full["pair_coverage"]["status"],
        "unmodeled": full["pair_coverage"]["unmodeled"],
        "bullet_query_count": full["bullet_consistency"]["query_count"],
        "bullet_status": full["bullet_consistency"]["status"],
        "full_result": record(full_path, "FULL_DYNAMIC_RESULT"),
    }


def run(args):
    root = Path(args.output_root).resolve()
    proposed = root / "proposed_src"
    ref_path = root / "runs/reference_final_v05/DYNAMIC_REFERENCE_REPORT.json"
    repair_path = root / "runs/mc04_repair_final_v07/MC04_REPAIR_VALIDATION.json"
    controls_path = root / "runs/controls_final_v05/DYNAMIC_CONTROL_REPORT.json"
    ref = load_bound(ref_path, "c5a3425b333a7fa761c9383fb840d869ad885a1260f1a772f4bf5b22ffc1d99a")
    repair = load_bound(repair_path, "3944dce61ca740f336278ea7bcfc34958fa89a987b969565e4e1cf8d2cc7337c")
    controls = load_bound(controls_path, "26061e48bd0cb2f86b90004b026c30fa203e6c5148c369092bc49f69daa3a1ec")

    sys.path.insert(0, str(proposed))
    suite = unittest.defaultTestLoader.discover(str(proposed), pattern="test_dynamic_geometry_v01.py")
    stream = io.StringIO()
    test_result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    unit = {
        "schema_version": 1,
        "status": "PASS" if test_result.wasSuccessful() and test_result.testsRun == 8 else "FAIL",
        "tests_run": test_result.testsRun,
        "failure_count": len(test_result.failures), "error_count": len(test_result.errors),
        "skipped_count": len(test_result.skipped), "runner_output": stream.getvalue(),
    }
    unit_path = root / "UNIT_TEST_REPORT.json"
    unit_path.write_text(json.dumps(unit, indent=2, sort_keys=True) + "\n")
    if unit["status"] != "PASS":
        raise RuntimeError("Unit tests failed")

    reference_rows = [detailed_coverage(row) for row in ref["results"]]
    physical = [row for row in reference_rows if row["modeled_solids"]]
    coverage = {
        "schema_version": 1,
        "release_id": "P3-G-DYNAMIC-PAIR-COVERAGE-0.1.0",
        "status": "COMPLETE_FOR_ALL_DECLARED_PHYSICAL_PAIRS_AND_TIME_SEGMENTS",
        "reference_count": len(reference_rows),
        "physical_reference_count": len(physical),
        "logical_only_not_applicable_count": len(reference_rows) - len(physical),
        "pair_time_segment_evaluations": sum(
            pair["evaluated_time_segments"] for row in physical for pair in row["pairs"]
        ),
        "pair_event_point_evaluations": sum(
            pair["evaluated_event_points"] for row in physical for pair in row["pairs"]
        ),
        "bullet_pair_point_queries": sum(row["bullet_query_count"] for row in physical),
        "physical_unmodeled_pairs": sorted({tuple(pair) for row in physical for pair in row["unmodeled"]}),
        "references": reference_rows,
        "interpretation": "Each nonempty declared modeled-solid inventory has its full unordered pair set evaluated on every reconstructed time segment and event/boundary point. MC05 A/B have no modeled solids and are explicitly N/A, not zero-query clear results.",
        "safety_label": None,
    }
    coverage["physical_unmodeled_pairs"] = [list(pair) for pair in coverage["physical_unmodeled_pairs"]]
    coverage_path = root / "DYNAMIC_PAIR_COVERAGE.json"
    coverage_path.write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n")

    source_paths = sorted(proposed.glob("*.py"))
    syntax_checks = []
    for path in source_paths:
        try:
            compile(path.read_text(), str(path), "exec")
            syntax_checks.append({"path": str(path.resolve()), "status": "PASS"})
        except SyntaxError as exc:
            syntax_checks.append({"path": str(path.resolve()), "status": "FAIL", "error": str(exc)})

    interface_path = root / "GEOMETRY_INTERFACE_READY.json"
    implementation = {
        "schema_version": 1,
        "release_id": "P3-G-DYNAMIC-GEOMETRY-IMPLEMENTATION-0.1.0",
        "status": "CANDIDATE_READY_FOR_MAIN_INTEGRATION",
        "profile": "DYNAMIC_FIXED_AABB_TRANSLATION_V01",
        "stable_interface": record(interface_path, "INITIAL_INTERFACE_RELEASE_PRESERVED"),
        "python_sources": [record(path, "CANDIDATE_SOURCE") for path in source_paths],
        "syntax_checks": syntax_checks,
        "unit_tests": record(unit_path, "UNIT_TEST_REPORT_8_OF_8"),
        "reference_evidence": record(ref_path, "12_RETAINED_REFERENCE_ACCOUNTING"),
        "repair_evidence": record(repair_path, "2_SELF_AUTHORED_MC04_REPAIR_EXECUTIONS"),
        "control_evidence": record(controls_path, "12_PROPOSITION_CONTROLS"),
        "coverage_evidence": record(coverage_path, "PAIR_BY_TIME_COVERAGE"),
        "optional_explicit_input": {
            "field": "world.grasp_offsets_m",
            "semantics": "object_id or ARM|object_id -> declared fixed xyz offset; absent means exactly zero",
        },
        "shared_src_modified": False,
        "old_D_E_F_modified": False,
        "model_calls": 0, "baseline_calls": 0, "human_labels_created": 0,
        "natural_programs": 0, "controlled_mutations": 0, "hardware_operations": 0,
        "safety_label": None, "stage3_go": False,
    }
    implementation_path = root / "GEOMETRY_IMPLEMENTATION_READY.json"
    implementation_path.write_text(json.dumps(implementation, indent=2, sort_keys=True) + "\n")

    mc04 = [row for row in ref["results"] if row["axis_id"] == "MC04_PERCEPTION"]
    physical_rows = [row for row in ref["results"]
                     if row["status"] != "NOT_APPLICABLE_LOGICAL_ONLY_NO_MODELED_SOLIDS"]
    checks = {
        "initial_interface_hash_preserved": sha256(interface_path) == "fc3c7b8502e9b0ce44e93ec0e0ea63b068c6bfa45999b65b48a80af37de51a71",
        "source_syntax_all_pass": all(row["status"] == "PASS" for row in syntax_checks),
        "unit_tests_8_of_8": unit["status"] == "PASS" and unit["tests_run"] == 8,
        "all_12_references_accounted": ref["case_count"] == 12,
        "reference_partition_8_clear_2_violation_2_na_0_inconclusive": (
            ref["no_forbidden_contact_count"] == 8 and ref["violation_count"] == 2
            and ref["not_applicable_count"] == 2 and ref["inconclusive_count"] == 0
        ),
        "all_10_physical_reference_coverages_pass": (
            len(physical_rows) == 10
            and all(row["pair_coverage"]["status"] == "PASS" for row in physical_rows)
        ),
        "all_10_physical_reconstructions_pass": (
            all(row["reconstruction_status"] == "PASS" for row in physical_rows)
        ),
        "all_10_physical_bullet_checks_pass": (
            all(row["bullet_consistency"]["status"] == "PASS" for row in physical_rows)
        ),
        "mc04_original_two_exact_violations_retained": (
            len(mc04) == 2 and all(row["status"] == "VIOLATIONS"
                                  and any(finding["pair"] == ["LEFT_gripper", "locator_fixture"]
                                          and finding["time_interval_s"] == [2.5, 5.0]
                                          for finding in row["findings"])
                                  for row in mc04)
        ),
        "mc04_forward_repair_2_of_2_pass": repair["status"] == "PASS" and repair["pass_count"] == 2,
        "old_mc04_results_not_overwritten": repair["old_retained_reference_results_overwritten"] is False,
        "controls_13_of_13_pass": controls["status"] == "PASS" and controls["pass_count"] == 13,
        "coverage_has_no_unmodeled_physical_pair": not coverage["physical_unmodeled_pairs"],
        "no_new_experimental_or_human_counts": all(
            value == 0 for value in (
                ref["model_calls"], ref["baseline_calls"], ref["human_labels_created"],
                ref["natural_programs"], ref["controlled_mutations"], ref["hardware_operations"],
                repair["model_calls"], repair["baseline_calls"], repair["human_labels_created"],
                repair["natural_programs"], repair["controlled_mutations"], repair["hardware_operations"],
                controls["model_calls"], controls["baseline_calls"], controls["human_labels_created"],
                controls["hardware_operations"],
            )
        ),
    }
    validation = {
        "schema_version": 1,
        "release_id": "P3-G-DYNAMIC-GEOMETRY-VALIDATION-0.1.0",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_COMPONENT_READY_WITH_ORIGINAL_MC04_DEFECT_AND_FORWARD_REPAIR_VALIDATED"
        if all(checks.values()) else "FAIL",
        "checks": checks,
        "reference_report": record(ref_path), "repair_report": record(repair_path),
        "control_report": record(controls_path), "coverage_report": record(coverage_path),
        "implementation_release": record(implementation_path),
        "report": record(root / "REPORT.md"), "integration_notes": record(root / "INTEGRATION.md"),
        "unit_test_report": record(unit_path),
        "pair_time_segment_evaluations": coverage["pair_time_segment_evaluations"],
        "pair_event_point_evaluations": coverage["pair_event_point_evaluations"],
        "bullet_pair_point_queries": coverage["bullet_pair_point_queries"],
        "stage3_decision": "REVISE",
        "stage4_frozen": False,
        "safety_label": None,
    }
    validation_path = root / "VALIDATION.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
    if validation["status"] == "FAIL":
        raise RuntimeError("Final G validation failed")

    handoff = {
        "schema_version": 1,
        "release_id": "P3-G-DYNAMIC-GEOMETRY-HANDOFF-0.1.0",
        "status": "COMPLETE_COMPONENT_READY_STAGE3_REVISE",
        "task": "Stage 3 G dynamic objects and contact evidence",
        "decision": "REVISE_STAGE3_COMPONENT_G_READY",
        "primary_files": {
            "report": record(root / "REPORT.md"), "validation": record(validation_path),
            "implementation": record(implementation_path), "coverage": record(coverage_path),
            "integration": record(root / "INTEGRATION.md"),
        },
        "evidence": {
            "retained_12_reference_report": record(ref_path),
            "mc04_forward_repair_validation": record(repair_path),
            "proposition_controls": record(controls_path),
            "unit_tests": record(unit_path),
        },
        "results": {
            "retained_reference_count": 12, "within_scope_clear_count": 8,
            "original_violation_count": 2, "not_applicable_count": 2,
            "inconclusive_count": 0, "repair_candidate_pass_count": 2,
            "control_pass_count": 13, "control_count": 13,
            "pair_time_segment_evaluations": coverage["pair_time_segment_evaluations"],
            "pair_event_point_evaluations": coverage["pair_event_point_evaluations"],
            "bullet_pair_point_queries": coverage["bullet_pair_point_queries"],
        },
        "main_action": "Keep both original MC04 positives; review and version the already published forward-only release-departure amendment. Do not modify the public contact lifecycle or old D/E/F evidence.",
        "limits": implementation["scope"] if "scope" in implementation else [
            "Fixed-orientation rigid AABB affine translations only.",
            "No support geometry/stability, rotation, articulated links, forces, friction, grasp force, or whole-robot safety claim.",
        ],
        "reproduction_commands": [
            "env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/paper3_g_pycache PYTHONPATH=src:01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src .venv-robotics/bin/python 01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src/run_dynamic_references_v01.py --project-root . --d-root 01_project/STAGE3_DEF_2026-09-06/outputs/D_contract_specs --main-integration 01_project/STAGE3_DEF_2026-09-06/MAIN_INTEGRATION --output /tmp/g_reference_repro",
            "env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/paper3_g_pycache PYTHONPATH=src:01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src .venv-robotics/bin/python -m unittest -v 01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src/test_dynamic_geometry_v01.py",
            "Repair and C10 control execution require local bubblewrap/seccomp namespace permission; exact locked commands and inputs are in each run's PRE_RUN_LOCK.json.",
        ],
        "accounting": {
            "model_calls": 0, "baseline_calls": 0, "human_labels_created": 0,
            "natural_programs": 0, "controlled_mutations": 0,
            "self_authored_repair_program_executions": 2,
            "self_authored_control_program_executions": 1,
            "hardware_operations": 0,
        },
        "shared_src_modified": False, "old_D_E_F_modified": False,
        "stage3_go": False, "stage4_frozen": False, "safety_label": None,
    }
    handoff_path = root / "HANDOFF.json"
    handoff_path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": handoff["status"], "handoff": str(handoff_path),
                      "sha256": sha256(handoff_path)}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
