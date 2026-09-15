"""Inspect one F01 reference seed while the scheduler is under qualification."""
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


async def main() -> None:
    spec = json.loads((HERE / "reference_tasks/R2V4-F01/SPEC.json").read_text(encoding="utf-8"))
    atoms = (HERE / "reference_tasks/R2V4-F01/reference_atoms.py").read_text(encoding="utf-8")
    capture = await execute(
        compose(atoms, "SERIAL", "SHORT", 0, "A_FULL_THEN_B_FULL"),
        spec,
        ROOT,
    )
    selected = {
        "process": capture.get("process"),
        "execution_lifecycle_complete": capture.get("execution_lifecycle_complete"),
        "child_lifecycle_report": capture.get("child_lifecycle_report"),
        "trusted_api_errors": capture.get("trusted_api_errors"),
        "call_audit": capture.get("call_audit"),
        "trusted_events": capture.get("trusted_events"),
    }
    print(json.dumps(selected, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
