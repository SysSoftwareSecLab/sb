import asyncio
from bridge_robot_api import Robot


async def _left_lane(robot: Robot) -> None:
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")


async def _right_lane(robot: Robot) -> None:
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")


async def _rq2_gate_protocol(robot: Robot) -> None:
    gate_receipt = robot.signal("rq2_gate")
    gate_version = gate_receipt.version

    for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", resource_id, 5)
        await robot.release_resource("LEFT", resource_id)

    await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_version)


async def run_task(robot: Robot) -> None:
    await _rq2_gate_protocol(robot)

    left_ready = robot.signal("left_ready")
    right_ready = robot.signal("right_ready")

    await asyncio.gather(
        _left_lane(robot),
        _right_lane(robot),
    )

    robot.clear_event("left_ready", expected_version=left_ready.version)
    robot.clear_event("right_ready", expected_version=right_ready.version)
