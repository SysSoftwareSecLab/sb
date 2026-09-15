import asyncio

from bridge_robot_api import Robot


async def _left_lane(robot: Robot) -> None:
    # Approach left_part from left_home to left_source, then grasp immediately.
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")

    # Transport held object to its target support zone.
    await robot.move("LEFT", "left_target")

    # Release on the named support zone, then immediately depart.
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")


async def _right_lane(robot: Robot) -> None:
    # Approach right_part from right_home to right_source, then grasp immediately.
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")

    # Transport held object to its target support zone.
    await robot.move("RIGHT", "right_target")

    # Release on the named support zone, then immediately depart.
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")


async def _rq2_gate_protocol(robot: Robot) -> None:
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 with LEFT in numeric order.
    for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", resource_id, 5)
        await robot.release_resource("LEFT", resource_id)

    # All three gap checks complete; signal rq2_gate exactly once.
    gate_receipt = robot.signal("rq2_gate")

    # Wait immediately after the signal for the exact active receipt.
    await robot.wait_event("rq2_gate", 5)

    # Clear exactly that version after the assigned protected scope.
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)


async def run_task(robot: Robot) -> None:
    # Joined concurrent scheduling for the rq2_gate producer/consumer protocol.
    gate_task = asyncio.create_task(_rq2_gate_protocol(robot))

    # Complete and clear the rq2_gate protocol before starting the dual-arm mission.
    await gate_task

    # Joined concurrent scheduling for the inherited dual-arm mission.
    await asyncio.gather(_left_lane(robot), _right_lane(robot))
