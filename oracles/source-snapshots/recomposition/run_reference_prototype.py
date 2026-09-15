"""Run the F01 reference prototype through the existing isolated runtime."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QUALITY = HERE.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
from runtime import execute

from frozen_composer import compose


def completed_moves(capture: dict) -> list[dict]:
    return [
        event
        for event in capture.get("trusted_events", [])
        if event.get("phase") == "complete" and event.get("action") == "move"
    ]


async def main() -> None:
    spec = json.loads((HERE / "reference_prototype/F01_SPEC.json").read_text(encoding="utf-8"))
    atoms = (HERE / "reference_prototype/F01_reference_atoms.py").read_text(encoding="utf-8")
    rows = []
    for schedule in ("SERIAL", "CONCURRENT"):
        for distance in ("SHORT", "LONG"):
            source = compose(atoms, schedule, distance, 0, "A_FULL_THEN_B_FULL")
            capture = await execute(source, spec, ROOT)
            rows.append(
                {
                    "schedule": schedule,
                    "distance": distance,
                    "status": capture.get("process", {}).get("status"),
                    "returncode": capture.get("process", {}).get("returncode"),
                    "lifecycle_complete": capture.get("execution_lifecycle_complete"),
                    "api_errors": capture.get("trusted_api_errors"),
                    "moves": [event.get("args") for event in completed_moves(capture)],
                    "move_events": [
                        {"phase": event.get("phase"), "time": event.get("time"), "args": event.get("args")}
                        for event in capture.get("trusted_events", [])
                        if event.get("action") == "move"
                    ],
                    "stderr": capture.get("process", {}).get("stderr"),
                }
            )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
