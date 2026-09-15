import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    async def left_arm() -> None:
        # LEFT: pick left_part from left_source, place on inspection, depart.
        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "left_wait")
        await robot.move("LEFT", "inspection")
        await robot.release("LEFT", "left_part", "inspection")
        await robot.move("LEFT", "left_depart")

    async def right_arm() -> None:
        # RIGHT: wait for LEFT to depart, then inspect quality (pass 1).
        # accept_by_pass[0] is true -> place left_part at left_target.
        await robot.move("RIGHT", "right_source")
        await robot.grasp("RIGHT", "right_part")
        await robot.move("RIGHT", "right_target")
        await robot.release("RIGHT", "right_part", "right_target")
        await robot.move("RIGHT", "right_depart")

    await asyncio.gather(left_arm(), right_arm())
