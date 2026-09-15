"""Exercise the first direct-P oracle and scheduler with a controlled error."""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QUALITY = HERE.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(QUALITY / "trace_dev_v1"))
from runtime import execute

from direct_p_oracle import evaluate, schedule_hash
from frozen_composer import SEEDS, compose


async def main() -> None:
    spec = json.loads((HERE / "reference_prototype/F01_SPEC.json").read_text(encoding="utf-8"))
    variants = {
        "SAFE_REFERENCE": (HERE / "reference_prototype/F01_reference_atoms.py").read_text(encoding="utf-8"),
        "MISSING_LOCK": (HERE / "reference_prototype/F01_missing_lock_atoms.py").read_text(encoding="utf-8"),
    }
    rows = []
    for variant, atoms in variants.items():
        for schedule, distance, seeds in (
            ("SERIAL", "SHORT", (0,)),
            ("SERIAL", "LONG", (0,)),
            ("CONCURRENT", "SHORT", SEEDS),
            ("CONCURRENT", "LONG", SEEDS),
        ):
            for seed in seeds:
                capture = await execute(
                    compose(atoms, schedule, distance, seed, "A_FULL_THEN_B_FULL"),
                    spec,
                    ROOT,
                )
                endpoint = evaluate(capture, spec)
                rows.append(
                    {
                        "variant": variant,
                        "schedule": schedule,
                        "distance": distance,
                        "seed": seed,
                        "lifecycle_complete": capture.get("execution_lifecycle_complete"),
                        "P": endpoint["P"],
                        "exposed": endpoint["exposed"],
                        "a_interval": endpoint["a_interval"],
                        "b_interval": endpoint["b_interval"],
                        "schedule_hash": schedule_hash(capture),
                    }
                )
    summary = {}
    for variant in variants:
        selected = [row for row in rows if row["variant"] == variant]
        summary[variant] = {
            "executions": len(selected),
            "lifecycles_complete": sum(row["lifecycle_complete"] for row in selected),
            "P_counts": dict(Counter(row["P"] for row in selected)),
            "distinct_schedule_hashes": len({row["schedule_hash"] for row in selected}),
            "concurrent_distinct_schedule_hashes": len(
                {row["schedule_hash"] for row in selected if row["schedule"] == "CONCURRENT"}
            ),
        }
    print(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
