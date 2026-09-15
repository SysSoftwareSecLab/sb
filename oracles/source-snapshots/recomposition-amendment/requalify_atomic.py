"""Replay existing v4 atomic captures with local, not pair-global, postconditions."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V4 = HERE.parent / "rq2_structure_preserving_recomposition_v4"
SOURCE_RUN = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4"
OUT = ROOT / "05_formal/rq2_structure_preserving_recomposition_v4_amendment_001"
sys.path.insert(0, str(V4))
from atomic_contract_oracle import dynamic_local_contract, static_local_contract
from amended_measurement import atomic_local_cleanup


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    manifest = read(V4 / "GENERATION_MANIFEST.json")
    rows = []
    for slot in manifest:
        spec = read(V4 / slot["spec_path"])
        folder = SOURCE_RUN / "generation" / slot["slot_id"]
        generation = read(folder / "RESULT.json")
        candidate = folder / "candidate.py"
        row = {
            "slot_id": slot["slot_id"], "family_id": slot["family_id"],
            "mechanism": slot["mechanism"], "profile": slot["profile"], "repeat": slot["repeat"],
            "generation_status": generation["status"], "interface_valid": bool(generation.get("interface_valid")),
            "atoms": [],
        }
        if not row["interface_valid"] or not candidate.exists():
            row.update(static_contract_ok=False, static_contract_errors=["NO_VALID_ATOMIC_SOURCE"], eligible=False)
            rows.append(row)
            continue
        source = candidate.read_text(encoding="utf-8")
        static = static_local_contract(source, spec)
        row.update(static_contract_ok=static["passed"], static_contract_errors=static["errors"])
        if not static["passed"]:
            row["eligible"] = False
            rows.append(row)
            continue
        for atom in ("A", "B"):
            capture_path = SOURCE_RUN / "atomic_qualification" / slot["slot_id"] / atom / "CAPTURE.json"
            capture = read(capture_path)
            dynamic = dynamic_local_contract(capture, spec, atom)
            cleanup = atomic_local_cleanup(capture, spec, atom)
            atom_row = {
                "atom": atom,
                "capture_path": str(capture_path.relative_to(ROOT)),
                "capture_sha256": sha(capture_path),
                "lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
                "process_status": capture.get("process", {}).get("status"),
                "returncode": capture.get("process", {}).get("returncode"),
                "api_error_count": len(capture.get("trusted_api_errors", [])),
                "dynamic_contract_ok": dynamic["passed"],
                "dynamic_contract_reason": dynamic["reason"],
                "local_cleanup_ok": cleanup["passed"],
                "local_cleanup_checks": cleanup["checks"],
            }
            atom_row["passed"] = (
                atom_row["lifecycle_complete"] and atom_row["process_status"] == "EXITED"
                and atom_row["returncode"] == 0 and atom_row["api_error_count"] == 0
                and atom_row["dynamic_contract_ok"] and atom_row["local_cleanup_ok"]
            )
            row["atoms"].append(atom_row)
        row["eligible"] = all(atom["passed"] for atom in row["atoms"])
        rows.append(row)
    eligible = [row for row in rows if row["eligible"]]
    profiles_by_family = {}
    for family_id in sorted({row["family_id"] for row in rows}):
        profiles_by_family[family_id] = sorted({row["profile"] for row in eligible if row["family_id"] == family_id})
    common = sorted(family_id for family_id, profiles in profiles_by_family.items() if profiles == ["deepseek_flash", "glm5"])
    mechanism_counts = Counter(next(row["mechanism"] for row in rows if row["family_id"] == family_id) for family_id in common)
    result = {
        "schema": "paper3.rq2.v4_amendment.atomic_requalification.v1",
        "status": "PASS_EXPECTED_90" if len(eligible) == 90 and len(common) == 22 and sorted(mechanism_counts.values()) == [4, 6, 6, 6] else "STOP_UNEXPECTED_QUALIFICATION_RESULT",
        "fixed_generation_slots": len(rows),
        "eligible_slots": len(eligible),
        "ineligible_slots": [row["slot_id"] for row in rows if not row["eligible"]],
        "common_two_model_families": common,
        "common_family_count": len(common),
        "mechanism_common_family_counts": dict(sorted(mechanism_counts.items())),
        "rows": rows,
        "external_model_calls_added": 0,
    }
    write_json(OUT / "AMENDED_ATOMIC_QUALIFICATION.json", result)
    print(json.dumps({key: result[key] for key in (
        "status", "fixed_generation_slots", "eligible_slots", "ineligible_slots",
        "common_family_count", "mechanism_common_family_counts", "external_model_calls_added",
    )}, ensure_ascii=False, indent=2))
    if not result["status"].startswith("PASS"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
