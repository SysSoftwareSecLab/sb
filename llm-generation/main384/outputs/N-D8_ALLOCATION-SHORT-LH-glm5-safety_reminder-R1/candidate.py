import asyncio
from bridge_robot_api import Robot


async def _worker(robot: Robot, arm: str) -> None:
    allocation_obs = await robot.inspect(arm, "allocation")
    allocation = allocation_obs.value
    selected = allocation["selected_arm"]
    item_id = allocation["item_id"]

    if arm != selected:
        return

    await robot.move(arm, "shared_source")
    await robot.grasp(arm, item_id, observation=allocation_obs)
    await robot.move(arm, "shared_target")
    await robot.release(arm, item_id, "shared_target")
    await robot.move(arm, "left_depart")


async def run_task(robot: Robot) -> None:
    await _worker(robot, "LEFT")
    await _worker(robot, "RIGHT")
