import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Phase 1: rq2_gap_0, rq2_gap_1, rq2_gap_2 checks with LEFT, in numeric order.
    for gap_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap_id, 5)
        try:
            pass
        finally:
            await robot.set_mode("LEFT", gap_id, "OFF")
            await robot.release_resource("LEFT", gap_id)

    # Phase 2: signal rq2_gate exactly once.
    gate_receipt = robot.signal("rq2_gate")

    # Phase 3: wait its exact active receipt exactly once, immediately.
    waited_receipt = await robot.wait_event("rq2_gate", 5)

    # Phase 4: protected scope is the inherited dual-arm mission.
    try:
        await _run_inherited_mission(robot, gate_receipt)
    finally:
        # Clear exactly that version after the assigned protected scope.
        robot.clear_event("rq2_gate", expected_version=gate_receipt.version)


async def _run_inherited_mission(robot: Robot, gate_receipt: object) -> None:
    # Serial scheduling for the inherited dual-arm mission.
    await _worker(robot, "LEFT", "left_part", "left_home", "left_source",
                  "left_target", "left_depart", gate_receipt)
    await _worker(robot, "RIGHT", "right_part", "right_home", "right_source",
                  "right_target", "right_depart", gate_receipt)


async def _worker(robot: Robot, arm: str, part_id: str, home_pose: str,
                  source_pose: str, target_pose: str, depart_pose: str,
                  gate_receipt: object) -> None:
    # Acquire fixture then tool, carrying the corresponding part to target
    # while owning both, release and depart, then release tool and fixture.
    fixture_acquired = False
    tool_acquired = False
    part_grasped = False

    try:
        await robot.acquire(arm, "fixture", 5)
        fixture_acquired = True

        await robot.acquire(arm, "tool", 5)
        tool_acquired = True

        # Approach from home to source, then immediately grasp.
        await robot.move(arm, source_pose)
        await robot.grasp(arm, part_id)
        part_grasped = True

        # Carry part to target using the active gate receipt matching the held object.
        await robot.move(arm, target_pose, receipt=gate_receipt)

        # Release at target, then immediately depart.
        await robot.release(arm, part_id, target_pose)
        part_grasped = False
        await robot.move(arm, depart_pose)
    finally:
        # Ensure part is released if something failed mid-transport.
        if part_grasped:
            try:
                await robot.release(arm, part_id, target_pose)
            except Exception:
                pass

        # Release tool then fixture (reverse acquisition order).
        if tool_acquired:
            try:
                await robot.set_mode(arm, "tool", "OFF")
                await robot.release_resource(arm, "tool")
            except Exception:
                pass

        if fixture_acquired:
            try:
                await robot.set_mode(arm, "fixture", "OFF")
                await robot.release_resource(arm, "fixture")
            except Exception:
                pass
