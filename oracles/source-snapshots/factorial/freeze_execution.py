"""Freeze natural execution, exposure accounting, and human packaging code."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


P = Path(__file__).resolve().parent
ROOT = P.parents[3]
RUN = ROOT / "05_formal/rq2_rq4_identifiable_confirmation_v1"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = P / "EXECUTION_IMPLEMENTATION_FREEZE.json"
    if output.exists():
        raise RuntimeError("Execution implementation already frozen")
    assert read(P / "SCIENTIFIC_FREEZE.json")["status"] == "FROZEN_READY_FOR_CAPABILITY_AND_NATURAL_COLLECTION"
    natural_responses = list((RUN / "generation").glob("*/RESPONSE.raw")) if (RUN / "generation").exists() else []
    assert not natural_responses, "Natural response exists before execution implementation freeze"
    files = [
        P / "SCIENTIFIC_FREEZE.json", P / "freeze_execution.py", P / "run_natural.py",
        P / "package_human_review.py", P / "HUMAN_REVIEW_GUIDE.md",
        P.parent / "formal_replacement_v2/collect.py", P.parent / "formal_replacement_v2/PUBLIC_API.md",
        P.parent.parent / "trace_dev_v1/runtime.py",
        ROOT / "01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src/geometry_interface_v01.py",
        ROOT / "01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src/dynamic_geometry_v01.py",
        P.parent.parent / "task2_evidence/evaluate.py", P.parent / "structural_batch/measure.py",
        P.parent.parent / "batch_7_9/evidence.py",
    ]
    value = {
        "status": "FROZEN_BEFORE_NATURAL_CALLS", "natural_calls_before_freeze": 0,
        "natural_slots": 320, "capability_results_required_before_natural": True,
        "execute_and_write_exposure_before_next_model_request": True,
        "candidate_execution": "bwrap read-only job sandbox",
        "geometry_runtime": "project .venv-robotics; pybullet 3.2.7",
        "files": [{"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size} for path in sorted(files)],
    }
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": value["status"], "files": len(files), "natural_slots": 320}, ensure_ascii=False))


if __name__ == "__main__":
    main()
