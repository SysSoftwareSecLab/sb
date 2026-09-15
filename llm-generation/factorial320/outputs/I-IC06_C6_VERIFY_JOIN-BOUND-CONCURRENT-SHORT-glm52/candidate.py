import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    async def left_branch() -> None:
        await robot.acquire("LEFT", "rq2_gap_0", 5)
        await robot.release_resource("LEFT", "rq2_gap_0")
        await robot.acquire("LEFT", "rq2_gap_1", 5)
        await robot.release_resource("LEFT", "rq2_gap_1")
        await robot.acquire("LEFT", "rq2_gap_2", 5)
        await robot.release_resource("LEFT", "rq2_gap_2")

        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "left_target")
        await robot.release("LEFT", "left_part", "left_target")
        await robot.move("LEFT", "left_depart")
        robot.signal("left_ready")

    async def right_branch() -> None:
        await robot.move("RIGHT", "right_source")
        await robot.grasp("RIGHT", "right_part")
        await robot.move("RIGHT", "right_target")
        await robot.release("RIGHT", "right_part", "right_target")
        await robot.move("RIGHT", "right_depart")
        robot.signal("right_ready")

    await asyncio.gather(left_branch(), right_branch())

    gate_receipt = robot.signal("rq2_gate")
    await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
