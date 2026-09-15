import asyncio

from bridge_robot_api import Robot


async def _left_branch(robot: Robot) -> None:
    # Approach left_part from left_home, then immediately grasp.
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")

    # Transport left_part to its target support zone.
    await robot.move("LEFT", "left_target")

    # Release left_part at left_target, then immediately depart.
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")

    # Signal left_ready for the join.
    robot.signal("left_ready", "left_part")


async def _right_branch(robot: Robot) -> None:
    # Approach right_part from right_home, then immediately grasp.
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")

    # Transport right_part to its target support zone.
    await robot.move("RIGHT", "right_target")

    # Release right_part at right_target, then immediately depart.
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")

    # Signal right_ready for the join.
    robot.signal("right_ready", "right_part")


async def _gap_checks(robot: Robot) -> None:
    # Acquire and release each gap resource with LEFT in numeric order.
    for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", resource_id, 5)
        await robot.release_resource("LEFT", resource_id)


async def run_task(robot: Robot) -> None:
    # Concurrent producer/consumer and inherited dual-arm mission.
    gate_task = asyncio.create_task(_gate_producer(robot))
    mission_task = asyncio.create_task(_mission(robot))

    await asyncio.gather(gate_task, mission_task)


async def _gate_producer(robot: Robot) -> None:
    # Signal rq2_gate exactly once.
    gate_receipt = robot.signal("rq2_gate", "rq2_gate")

    # Complete all three rq2_gap resource checks before waiting.
    await _gap_checks(robot)

    # Wait for the exact active rq2_gate receipt once.
    waited = await robot.wait_event("rq2_gate", 10)
    assert waited.version == gate_receipt.version

    # Keep rq2_gate active through the complete inherited dual-arm mission.
    await _mission(robot)

    # Clear exactly the signaled version after the protected scope.
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)


async def _mission(robot: Robot) -> None:
    # Joined concurrent scheduling for both verifier branches.
    left_task = asyncio.create_task(_left_branch(robot))
    right_task = asyncio.create_task(_right_branch(robot))

    await asyncio.gather(left_task, right_task)
