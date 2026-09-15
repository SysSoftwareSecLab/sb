import asyncio
from bridge_robot_api import Robot


async def _acquire_gap_resources(robot: Robot) -> None:
    for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", resource_id, 120)
    for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.release_resource("LEFT", resource_id)


async def _left_arm_mission(robot: Robot) -> None:
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")


async def _right_arm_mission(robot: Robot) -> None:
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")


async def _dual_arm_mission(robot: Robot) -> None:
    await asyncio.gather(_left_arm_mission(robot), _right_arm_mission(robot))


async def run_task(robot: Robot) -> None:
    await _acquire_gap_resources(robot)
    gate_receipt = robot.signal("rq2_gate")
    await robot.wait_event("rq2_gate", 120)
    await _dual_arm_mission(robot)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
