import asyncio

from bridge_robot_api import Robot


async def _left_branch(robot: Robot) -> None:
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")


async def _right_branch(robot: Robot) -> None:
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")


async def _rq2_gate_protocol(robot: Robot) -> None:
    gate_receipt = robot.signal("rq2_gate")

    for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", resource_id, 5)
        await robot.release_resource("LEFT", resource_id)

    await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)


async def run_task(robot: Robot) -> None:
    gate_task = asyncio.create_task(_rq2_gate_protocol(robot))
    mission_task = asyncio.create_task(
        asyncio.gather(_left_branch(robot), _right_branch(robot))
    )

    await gate_task
    await mission_task
