import asyncio
from bridge_robot_api import Robot


async def _rq2_gate_protocol(robot: Robot) -> None:
    """Serial rq2_gate producer/consumer: check three gaps, signal, wait, clear."""
    for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", resource_id, 5)
        await robot.release_resource("LEFT", resource_id)

    gate_receipt = robot.signal("rq2_gate")
    waited_receipt = await robot.wait_event("rq2_gate", 5)
    if waited_receipt.version != gate_receipt.version:
        raise RuntimeError("rq2_gate active receipt version mismatch")
    robot.clear_event("rq2_gate", expected_version=waited_receipt.version)


async def _left_lane(robot: Robot) -> None:
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")
    robot.signal("left_ready")


async def _right_lane(robot: Robot) -> None:
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
    robot.signal("right_ready")


async def run_task(robot: Robot) -> None:
    # Complete and clear the rq2_gate protocol before the inherited dual-arm mission.
    await _rq2_gate_protocol(robot)

    # Serial scheduling for the inherited dual-arm mission.
    await _left_lane(robot)
    await _right_lane(robot)

    # Join: wait both readiness events, then clear them so none remain active at return.
    left_receipt = await robot.wait_event("left_ready", 5)
    right_receipt = await robot.wait_event("right_ready", 5)
    robot.clear_event("left_ready", expected_version=left_receipt.version)
    robot.clear_event("right_ready", expected_version=right_receipt.version)
