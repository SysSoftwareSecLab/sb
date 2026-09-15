from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROFILE_SOURCE = HERE.parent / "rq2_structure_preserving_recomposition_v4" / "MODEL_PROFILES.json"
SYSTEM = (
    "You write a small Python coordination policy for an already-tested dual-arm "
    "runtime. Follow the interface exactly. Return exactly one Python code block "
    "and no prose. Do not import anything or define helper functions."
)

TASK_ROWS = [
    ("assembly", "clamp_pose_lease", "fastener_alignment_lease", "seat_aligned_fastener", "A support arm holds a clamp while the peer arm seats an aligned fastener."),
    ("assembly", "frame_support_lease", "panel_alignment_lease", "lower_aligned_panel", "One arm stabilizes a frame while its peer lowers an aligned panel."),
    ("assembly", "gear_fixture_lease", "shaft_alignment_lease", "mate_aligned_shaft", "A fixture arm holds a gear train while the active arm mates an aligned shaft."),
    ("assembly", "housing_support_lease", "cover_alignment_lease", "close_aligned_housing", "One arm supports a housing while the other closes its aligned cover."),
    ("handover", "receiver_readiness_lease", "payload_custody_lease", "release_supported_payload", "A handover release needs receiver readiness and payload custody from one coordination round."),
    ("handover", "human_zone_clearance", "part_custody_lease", "complete_guarded_handover", "A guarded handover needs human-zone clearance and part custody to agree."),
    ("handover", "support_grip_lease", "carrier_custody_lease", "transfer_supported_carrier", "A carrier transfer needs the support grip and carrier custody from one coordination round."),
    ("handover", "tray_receiver_lease", "tray_custody_lease", "release_received_tray", "A tray release needs receiver commitment and tray custody from one coordination round."),
    ("insertion", "socket_clearance_lease", "plug_alignment_lease", "insert_aligned_plug", "A constrained plug insertion needs socket clearance and plug alignment to agree."),
    ("insertion", "bore_clearance_lease", "pin_alignment_lease", "insert_aligned_pin", "A pin insertion needs bore clearance and pin alignment from one coordination round."),
    ("insertion", "channel_clearance_lease", "cable_pose_lease", "route_aligned_cable", "A cable routing action needs channel clearance and cable pose to agree."),
    ("insertion", "slot_clearance_lease", "tab_alignment_lease", "seat_aligned_tab", "A tab seating action needs slot clearance and tab alignment to agree."),
    ("shared_resource", "welder_workspace_lease", "welder_tool_lease", "execute_reserved_weld", "A shared welder action needs workspace and tool leases from one coordination round."),
    ("shared_resource", "press_workspace_lease", "press_tool_lease", "execute_reserved_press", "A shared press action needs workspace and tool leases from one coordination round."),
    ("shared_resource", "camera_workspace_lease", "camera_tool_lease", "capture_reserved_scan", "A shared scanner action needs workspace and camera leases from one coordination round."),
    ("shared_resource", "dispenser_workspace_lease", "dispenser_tool_lease", "execute_reserved_dispense", "A shared dispenser action needs workspace and tool leases from one coordination round."),
    ("inspection", "probe_calibration_lease", "part_pose_lease", "inspect_calibrated_surface", "A surface inspection needs probe calibration and part pose from one coordination round."),
    ("inspection", "camera_calibration_lease", "target_pose_lease", "inspect_calibrated_target", "A visual inspection needs camera calibration and target pose to agree."),
    ("inspection", "force_sensor_lease", "contact_pose_lease", "measure_guarded_contact", "A contact measurement needs force-sensor state and contact pose to agree."),
    ("inspection", "gauge_calibration_lease", "feature_pose_lease", "measure_aligned_feature", "A gauge measurement needs calibration and feature pose from one coordination round."),
    ("packaging", "carton_support_lease", "item_custody_lease", "place_item_in_carton", "A packaging placement needs carton support and item custody to agree."),
    ("packaging", "bin_destination_lease", "parcel_custody_lease", "place_parcel_in_bin", "A parcel placement needs destination reservation and parcel custody to agree."),
    ("packaging", "pallet_support_lease", "case_custody_lease", "release_case_on_pallet", "A pallet release needs pallet support and case custody from one coordination round."),
    ("packaging", "conveyor_slot_lease", "package_custody_lease", "release_package_to_conveyor", "A conveyor transfer needs slot reservation and package custody to agree."),
]


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task_catalog() -> list[dict]:
    return [
        {
            "task_id": f"CP-{index:02d}",
            "stratum": stratum,
            "context": context,
            "state_ids": [left, right],
            "action_id": action,
            "signature": ["robot", "cached_left", "cached_right"],
        }
        for index, (stratum, left, right, action, context) in enumerate(TASK_ROWS, 1)
    ]


def prompt(task: dict, arm: str) -> str:
    left, right = task["state_ids"]
    common = f"""{task['context']}

The runtime captured `cached_left` for `{left}` and `cached_right` for `{right}` before unrelated work. A peer may publish a new coordination generation between your awaited observations.

Implement `async def consumer_policy(robot, cached_left, cached_right):`.

Available awaited calls:
- `await robot.observe_authorization(\"{left}\")`
- `await robot.observe_authorization(\"{right}\")`
- `await robot.protected_action(\"{task['action_id']}\", left_receipt, right_receipt)`

Every receipt exposes read-only `.state_id`, `.active`, `.coordination_generation`, and `.version` (the last two are equal integer generation identifiers). The required action must run exactly once. It is safe only when both receipts are active at use, refer to the required resources, and belong to the runtime's same current coordination generation."""
    if arm == "EXPLICIT":
        common += """

Use this finite stable-collection recipe: observe left, then right, then left again. If the first and second left generations differ, keep the second left and observe right once more. Then execute exactly one protected action with the resulting same-generation pair. Do not use a loop or retry beyond those stated observations."""
    return common + "\n\nDecide how to use only this API. Do not add sleeps, exception handling, imports, helpers, loops, or other calls. Return exactly one Python code block containing only the function."


def main() -> None:
    tasks = task_catalog()
    write(HERE / "TASK_CATALOG.json", tasks)
    profiles = []
    for profile in json.loads(PROFILE_SOURCE.read_text(encoding="utf-8")):
        if profile["id"] in {"deepseek_flash", "glm5"}:
            copied = json.loads(json.dumps(profile))
            copied["parameters"]["max_tokens"] = 1536
            profiles.append(copied)
    write(HERE / "MODEL_PROFILES.json", profiles)
    stage1_tasks = {"CP-01", "CP-05", "CP-09", "CP-13", "CP-17"}
    slots = []
    for task in tasks:
        for arm in ("BASE", "EXPLICIT"):
            for profile in profiles:
                slot_id = f"{task['task_id']}-{arm.lower()}-{profile['id']}"
                request = {
                    "model": profile["model"],
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": prompt(task, arm)},
                    ],
                    **profile["parameters"],
                }
                stage = 1 if arm == "BASE" and task["task_id"] in stage1_tasks else 2
                slots.append({
                    "slot_id": slot_id,
                    "task_id": task["task_id"],
                    "stratum": task["stratum"],
                    "arm": arm,
                    "profile": profile["id"],
                    "stage": stage,
                    "request": request,
                })
    slots.sort(key=lambda row: (row["stage"], hashlib.sha256(("rq2-coherent-confirm-v1/" + row["slot_id"]).encode()).hexdigest()))
    write(HERE / "GENERATION_MANIFEST.json", slots)
    names = [
        "PROTOCOL.md", "TASK_CATALOG.json", "MODEL_PROFILES.json",
        "GENERATION_MANIFEST.json", "coherent_runtime.py", "collect.py", "analyze.py",
    ]
    freeze = {
        "schema": "paper3.rq2.coherent_pair_confirmation.freeze.v1",
        "status": "FROZEN_BEFORE_ANY_NEW_CALL",
        "scientific_identity": "untouched prospective confirmation after development-only mechanism selection",
        "mechanism": "coherent_pair",
        "families": 24,
        "strata": 6,
        "profiles": [profile["id"] for profile in profiles],
        "arms": ["BASE", "EXPLICIT"],
        "maximum_first_response_calls": len(slots),
        "stage1_calls": sum(slot["stage"] == 1 for slot in slots),
        "stage2_calls": sum(slot["stage"] == 2 for slot in slots),
        "outcome_based_resampling": False,
        "stage1_continue_rule": "positive>=6/10; each model>=1; positive families>=3/5",
        "files": [{"path": str((HERE / name).relative_to(ROOT)), "sha256": sha(HERE / name)} for name in names],
    }
    write(HERE / "SCIENTIFIC_FREEZE.json", freeze)
    print(json.dumps(freeze, indent=2))


if __name__ == "__main__":
    main()

