import asyncio
from bridge_robot_api import Robot


async def _inspect_allocation(robot: Robot, arm: str):
    return await robot.inspect(arm, "allocation")


async def _selected_transport(robot: Robot, arm: str, alloc_obs, home_pose: str):
    await robot.move(arm, "shared_source")
    await robot.grasp(arm, "shared_part", observation=alloc_obs)
    await robot.move(arm, "shared_target")
    await robot.release(arm, "shared_part", "shared_target")
    await robot.move(arm, "left_depart" if arm == "LEFT" else "right_home")


async def _candidate_left(robot: Robot, alloc_obs):
    await _inspect_allocation(robot, "LEFT")
    await _selected_transport(robot, "LEFT", alloc_obs, "left_home")


async def _candidate_right(robot: Robot, alloc_obs):
    await _inspect_allocation(robot, "RIGHT")


async def run_task(robot: Robot):
    left_obs = await _inspect_allocation(robot, "LEFT")
    right_obs = await _inspect_allocation(robot, "RIGHT")

    selected = left_obs.value.get("selected_arm")
    if selected == "LEFT":
        await _selected_transport(robot, "LEFT", left_obs, "left_home")
    else:
        await _selected_transport(robot, "RIGHT", right_obs, "right_home")
