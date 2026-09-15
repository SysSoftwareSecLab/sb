import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # LEFT: left_home -> left_source -> grasp left_part -> left_wait -> inspection
    # -> release left_part@inspection (increments quality) -> grasp left_part ->
    # left_target -> release left_part@left_target -> left_depart
    # RIGHT: right_home -> right_source -> grasp right_part -> right_target
    # -> release right_part@right_target -> right_depart
    # Order: LEFT places at inspection and departs before RIGHT inspects quality.

    async def left_arm() -> None:
        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "left_wait")
        await robot.move("LEFT", "inspection")
        await robot.release("LEFT", "left_part", "inspection")
        await robot.move("LEFT", "left_wait")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "left_target")
        await robot.release("LEFT", "left_part", "left_target")
        await robot.move("LEFT", "left_depart")

    async def right_arm() -> None:
        await robot.move("RIGHT", "right_source")
        await robot.grasp("RIGHT", "right_part")
        await robot.move("RIGHT", "right_target")
        await robot.release("RIGHT", "right_part", "right_target")
        await robot.move("RIGHT", "right_depart")

    async def right_inspect_quality() -> None:
        # Pass 1: accept_by_pass[0] is true -> left_target already selected.
        await robot.inspect("RIGHT", "quality")
        # Pass 2: accept_by_pass[1] is true -> left_target already selected.
        await robot.refresh("RIGHT", "quality")

    async def right_sequence() -> None:
        await right_arm()
        await right_inspect_quality()

    left_task = asyncio.create_task(left_arm())
    right_task = asyncio.create_task(right_sequence())
    await left_task
    await right_task
