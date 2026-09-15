"""Build the fixed, temporally balanced 96-slot atomic-generation manifest."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
SYSTEM = (
    "You are generating code for a fixed scientific robot-programming benchmark. "
    "Follow the user contract exactly and return only the requested code block."
)


def read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    if (HERE / "SCIENTIFIC_FREEZE.json").exists():
        raise RuntimeError("scientific freeze exists; generation manifest cannot be rebuilt")
    catalog = read(HERE / "REFERENCE_TASK_CATALOG.json")
    profiles = {row["id"]: row for row in read(HERE / "MODEL_PROFILES.json")}
    slots = []
    # Interleave providers and rotate the family order in repeat 2 so temporal
    # service drift is not aliased with one model, mechanism, or repeat.
    for repeat in (1, 2):
        family_rows = list(catalog)
        if repeat == 2:
            family_rows = family_rows[12:] + family_rows[:12]
        for family_index, task in enumerate(family_rows):
            profile_order = ("deepseek_flash", "glm5")
            if (family_index + repeat) % 2:
                profile_order = tuple(reversed(profile_order))
            for profile_id in profile_order:
                profile = profiles[profile_id]
                prompt_path = HERE / task["prompt_path"]
                spec_path = HERE / task["spec_path"]
                prompt = prompt_path.read_text(encoding="utf-8")
                request = {
                    "model": profile["model"],
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    **profile["parameters"],
                }
                slots.append(
                    {
                        "slot_index": len(slots),
                        "slot_id": f'{task["family_id"]}--{profile_id}--R{repeat}',
                        "family_id": task["family_id"],
                        "mechanism": task["mechanism"],
                        "profile": profile_id,
                        "repeat": repeat,
                        "prompt_path": task["prompt_path"],
                        "prompt_sha256": sha(prompt_path),
                        "spec_path": task["spec_path"],
                        "spec_sha256": sha(spec_path),
                        "serial_policy": task["serial_policy"],
                        "request": request,
                    }
                )
    write_json(HERE / "GENERATION_MANIFEST.json", slots)
    print(json.dumps({"status": "BUILT", "slots": len(slots), "profiles": sorted(profiles)}))


if __name__ == "__main__":
    main()
