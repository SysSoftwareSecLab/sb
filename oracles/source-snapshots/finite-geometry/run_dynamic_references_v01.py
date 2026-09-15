"""Run Stage 3 G dynamic geometry over the eight retained D reference traces."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from geometry_interface_v01 import evaluate_dynamic_evidence


AXES = {"MC01_SCHEDULER", "MC02_DEPENDENCY", "MC03_RECOVERY",
        "MC04_PERCEPTION", "MC05_RESOURCE", "MC06_LOOP_STATE"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def merge_patch(target, patch):
    if not isinstance(patch, dict):
        return json.loads(json.dumps(patch))
    result = dict(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


def effective_spec(d_root, pair, variant):
    base_row = next(row for row in pair["base_specs"] if row["variant"] == variant)
    base_path = d_root / base_row["path"]
    if sha256(base_path) != base_row["sha256"]:
        raise RuntimeError("D base-spec hash mismatch")
    spec = json.loads(base_path.read_text())
    bindings = []
    for amendment_row in pair["amendments"]:
        path = d_root / amendment_row["path"]
        actual = sha256(path)
        if actual != amendment_row["sha256"]:
            raise RuntimeError("D amendment hash mismatch")
        amendment = json.loads(path.read_text())
        applies = amendment.get("applies_to", [])
        task_id = spec["task_id"]
        if not any((isinstance(row, str) and row == task_id)
                   or (isinstance(row, dict) and row.get("task_id") == task_id)
                   for row in applies):
            raise RuntimeError(f"D amendment does not apply to {task_id}")
        spec = merge_patch(spec, amendment["common_merge_patch"])
        spec = merge_patch(spec, amendment.get("variant_merge_patches", {}).get(variant, {}))
        bindings.append({"path": str(path.resolve()), "sha256": actual,
                         "version": amendment_row["version"],
                         "effective_spec_sha256_after_layer": json_sha256(spec)})
    return spec, {"base": {"path": str(base_path.resolve()), "sha256": base_row["sha256"]},
                  "amendments": bindings, "effective_spec_sha256": json_sha256(spec)}


def compact(result, full_path):
    bullet = result["bullet_consistency"]
    return {
        "task_id": result["task_id"],
        "axis_id": result["axis_id"],
        "variant": result["variant"],
        "status": result["status"],
        "trace_complete": result["trace_complete"],
        "pair_coverage": result["pair_coverage"],
        "motion_segment_count": len(result["motion_segments"]),
        "move_count": len(result["move_reconstruction"]),
        "attachment_count": len(result["attachment_reconstruction"]),
        "contact_windows": result["contact_windows"],
        "allowed_contact_window_count": len(result["allowed_contact_windows"]),
        "forbidden_finding_count": len(result["findings"]),
        "findings": result["findings"],
        "reconstruction_status": result["reconstruction_checks"]["status"],
        "snapshot_check_count": result["reconstruction_checks"]["snapshot_checks"]["check_count"],
        "bullet_consistency": {key: bullet[key] for key in
                               ("status", "engine", "query_count", "positive_or_boundary_query_count",
                                "negative_query_count", "disagreement_count")},
        "full_result": {"path": str(full_path.resolve()), "sha256": sha256(full_path)},
        "safety_label": None,
    }


def no_modeled_solids_result(spec):
    """Disclose a logical-only reference without manufacturing a clear claim."""
    return {
        "schema_version": 1,
        "profile": "DYNAMIC_FIXED_AABB_TRANSLATION_V01",
        "task_id": spec["task_id"], "axis_id": spec["axis_id"], "variant": spec["variant"],
        "status": "NOT_APPLICABLE_LOGICAL_ONLY_NO_MODELED_SOLIDS",
        "trace_complete": True,
        "pair_coverage": {
            "status": "NOT_APPLICABLE_NO_MODELED_SOLIDS",
            "inventory": {"status": "PASS", "modeled_solids": [],
                          "expected_pair_count": 0, "declared_pair_count": 0,
                          "excluded_pair_count": 0, "duplicate_declared_pair": False,
                          "missing_pairs": [], "extra_pairs": [],
                          "declared_and_excluded_overlap": []},
            "time_segment_count": 0, "pairs": [], "unmodeled": [],
        },
        "motion_segments": [], "move_reconstruction": [],
        "attachment_reconstruction": [], "contact_windows": [],
        "allowed_contact_windows": [], "permission_windows": [],
        "permission_errors": [], "findings": [], "initial_overlap_pairs": [],
        "reconstruction_checks": {"status": "NOT_APPLICABLE_NO_MODELED_SOLIDS",
                                  "snapshot_checks": {"status": "NOT_APPLICABLE", "check_count": 0,
                                                      "failures": []},
                                  "failures": [], "independent_replay_errors": []},
        "bullet_consistency": {
            "status": "NOT_APPLICABLE_NO_MODELED_SOLIDS", "engine": "NOT_INSTANTIATED",
            "query_count": 0, "positive_or_boundary_query_count": 0,
            "negative_query_count": 0, "disagreement_count": 0,
            "disagreements": [], "queries": [],
        },
        "continuous_method": "NOT_APPLICABLE_NO_MODELED_SOLIDS",
        "logical_support_treatment": "NOT_A_GEOMETRY_BODY",
        "scope": "No physical proposition: the published reference declares zero modeled solids and zero collision pairs.",
        "safety_label": None,
    }


def run(args):
    project = Path(args.project_root).resolve()
    d_root = Path(args.d_root).resolve()
    integration = Path(args.main_integration).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    full_dir = output / "full_results"
    full_dir.mkdir(parents=True, exist_ok=True)

    ready_path = d_root / "CONTRACT_READY_v0.1.0-candidate.4.json"
    matrix_path = d_root / "PAIR_MATRIX_v0.1.0-candidate.3.json"
    if sha256(ready_path) != "0c8335488c7e9da997196fb330cc9ac048fde4cfbe0b052a1440aaa736cc2ed3":
        raise RuntimeError("Unexpected D candidate-4 release hash")
    if sha256(matrix_path) != "195217064649e06714e48bc7bd118e0376168f1bda7328659996db2642a01044":
        raise RuntimeError("Unexpected D spec-candidate-3 release hash")
    matrix = json.loads(matrix_path.read_text())

    integration_validation_path = integration / "VALIDATION.json"
    integration_validation = json.loads(integration_validation_path.read_text())
    reference_report_path = integration / integration_validation["reference_results"]["report"]
    if sha256(reference_report_path) != integration_validation["reference_results"]["sha256"]:
        raise RuntimeError("Main retained reference report hash mismatch")
    reference_report = json.loads(reference_report_path.read_text())
    retained = {row["task_id"]: row for row in reference_report["results"]}

    results = []
    bindings = []
    for pair in matrix["effective_pairs"]:
        if pair["axis_id"] not in AXES:
            continue
        for variant in ("A", "B"):
            spec, spec_binding = effective_spec(d_root, pair, variant)
            retained_row = retained[spec["task_id"]]
            trace_path = integration / "reference_run" / (spec["task_id"] + "_TRACE.json")
            trace_hash = sha256(trace_path)
            trace = json.loads(trace_path.read_text())
            if trace.get("event_source") != "EXTERNAL_CONTROLLER_NOT_CANDIDATE_STDOUT":
                raise RuntimeError("Trace event source is not the external controller")
            reference_row = next(row for row in pair["references"] if row["variant"] == variant)
            if retained_row["source"]["sha256"] != reference_row["sha256"]:
                raise RuntimeError("Retained trace source does not match D pair manifest")
            if spec["world"].get("modeled_solids"):
                result = evaluate_dynamic_evidence(spec, trace["trusted_events"], trace["logical"])
            else:
                result = no_modeled_solids_result(spec)
            full_path = full_dir / (spec["task_id"] + "_DYNAMIC_GEOMETRY.json")
            full_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            results.append(compact(result, full_path))
            bindings.append({"task_id": spec["task_id"], "variant": variant,
                             "spec": spec_binding,
                             "reference": {"path": str((d_root / reference_row["path"]).resolve()),
                                           "sha256": reference_row["sha256"]},
                             "retained_trace": {"path": str(trace_path.resolve()), "sha256": trace_hash},
                             "retained_logical_status": trace["logical"]["status"]})

    source_files = [
        Path(__file__),
        Path(__file__).with_name("geometry_interface_v01.py"),
        Path(__file__).with_name("dynamic_geometry_v01.py"),
    ]
    report = {
        "schema_version": 1,
        "release_id": "P3-G-DYNAMIC-GEOMETRY-REFERENCE-RUN-0.1.0",
        "status": "COMPLETE_12_REFERENCE_ACCOUNTING_WITH_MC04_RELEASE_CONTACT_VIOLATIONS",
        "profile": "DYNAMIC_FIXED_AABB_TRANSLATION_V01",
        "D_bindings": {
            "contract": {"path": str(ready_path.resolve()), "sha256": sha256(ready_path)},
            "pair_manifest": {"path": str(matrix_path.resolve()), "sha256": sha256(matrix_path)},
        },
        "main_integration_bindings": {
            "validation": {"path": str(integration_validation_path.resolve()),
                           "sha256": sha256(integration_validation_path)},
            "reference_report": {"path": str(reference_report_path.resolve()),
                                 "sha256": sha256(reference_report_path)},
        },
        "source_bindings": [{"path": str(path.resolve()), "sha256": sha256(path)}
                            for path in source_files],
        "case_bindings": bindings,
        "case_count": len(results),
        "no_forbidden_contact_count": sum(row["status"] == "NO_FORBIDDEN_CONTACT_IN_DECLARED_FIXED_AABB_TRANSLATIONS"
                                          for row in results),
        "violation_count": sum(row["status"] == "VIOLATIONS" for row in results),
        "not_applicable_count": sum(row["status"] == "NOT_APPLICABLE_LOGICAL_ONLY_NO_MODELED_SOLIDS"
                                    for row in results),
        "inconclusive_count": sum(row["status"].startswith("INCONCLUSIVE") or row["status"] == "GEOMETRY_DISAGREEMENT"
                                  for row in results),
        "results": results,
        "interpretation": "All 12 retained calibration references are accounted for. Eight (MC01 plus MC02/03/06) have no forbidden contact in their declared fixed-AABB translations; both MC04 references retain a real post-release stationary contact violation; MC05 A/B declare no modeled solids and are explicitly not applicable to this physical proposition. This is tool evidence, not a safety label or natural sample result.",
        "model_calls": 0,
        "baseline_calls": 0,
        "human_labels_created": 0,
        "natural_programs": 0,
        "controlled_mutations": 0,
        "hardware_operations": 0,
        "safety_label": None,
    }
    report_path = output / "DYNAMIC_REFERENCE_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--d-root", required=True)
    parser.add_argument("--main-integration", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps({"case_count": report["case_count"],
                      "no_forbidden_contact_count": report["no_forbidden_contact_count"],
                      "violation_count": report["violation_count"],
                      "inconclusive_count": report["inconclusive_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
