import asyncio
from bridge_robot_api import Robot


async def _left_lane(robot: Robot) -> None:
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_target")
    await robot.move("LEFT", "left_depart")


async def _right_lane(robot: Robot) -> None:
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_target")
    await robot.move("RIGHT", "right_depart")


async def _inherited_mission(robot: Robot) -> None:
    await _left_lane(robot)
    await _right_lane(robot)


async def run_task(robot: Robot) -> None:
    gate_receipt = robot.signal("rq2_gate")

    await robot.acquire("LEFT", "rq2_gap_0", 5)
    await robot.release_resource("LEFT", "rq2_gap_0")
    await robot.acquire("LEFT", "rq2_gap_1", 5)
    await robot.release_resource("LEFT", "rq2_gap_1")
    await robot.acquire("LEFT", "rq2_gap_2", 5)
    await robot.release_resource("LEFT", "rq2_gap_2")

    await robot.wait_event("rq2_gate", 5)

    await _inherited_mission(robot)

    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
