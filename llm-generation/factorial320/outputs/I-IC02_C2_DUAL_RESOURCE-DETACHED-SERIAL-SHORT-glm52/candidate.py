import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # SERIAL structure: complete the rq2_gate protocol first, then run the
    # inherited dual-arm mission serially (LEFT worker, then RIGHT worker).

    # --- rq2_gap resource checks (LEFT, numeric order) ---
    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 5)
        try:
            await robot.release_resource("LEFT", gap)
        finally:
            # Best-effort release if release_resource did not already free it.
            try:
                await robot.release_resource("LEFT", gap)
            except Exception:
                pass

    # --- rq2_gate protocol: signal exactly once, wait once, clear after scope ---
    gate_receipt = robot.signal("rq2_gate")
    try:
        waited = await robot.wait_event("rq2_gate", 5)
        # Protected scope: the inherited dual-arm mission runs while the gate
        # is active, then the exact waited version is cleared.
        await _run_dual_arm_mission(robot)
    finally:
        robot.clear_event("rq2_gate", expected_version=waited.version)


async def _run_dual_arm_mission(robot: Robot) -> None:
    await _worker(robot, "LEFT", "left_part", "left_home", "left_source",
                  "left_target", "left_depart")
    await _worker(robot, "RIGHT", "right_part", "right_home", "right_source",
                  "right_target", "right_depart")


async def _worker(robot: Robot, arm: str, part: str, home: str, source: str,
                  target: str, depart: str) -> None:
    # Acquire fixture then tool; try/finally releases any acquired controllers.
    await robot.acquire(arm, "fixture", 5)
    fixture_owned = True
    tool_owned = False
    try:
        await robot.acquire(arm, "tool", 5)
        tool_owned = True

        # Approach from declared start_pose to the object's current support.
        await robot.move(arm, source)
        # Immediately grasp in the same virtual moment after the approach.
        await robot.grasp(arm, part)

        # Carry the part to its target while owning both controllers.
        await robot.move(arm, target)
        # Release on the target support zone, then immediately depart.
        await robot.release(arm, part, target)
        await robot.move(arm, depart)

        # Release tool then fixture (reverse acquisition order).
        await robot.release_resource(arm, "tool")
        tool_owned = False
        await robot.release_resource(arm, "fixture")
        fixture_owned = False
    finally:
        if tool_owned:
            try:
                await robot.release_resource(arm, "tool")
            except Exception:
                pass
        if fixture_owned:
            try:
                await robot.release_resource(arm, "fixture")
            except Exception:
                pass
