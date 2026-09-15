import asyncio
from bridge_robot_api import Robot


async def _inspect_allocation(robot: Robot, arm: str) -> str:
    obs = await robot.inspect(arm, "allocation")
    return obs.observation_id


async def _selected_transport(robot: Robot, arm: str, home_pose: str, depart_pose: str) -> None:
    alloc_obs_id = await _inspect_allocation(robot, arm)

    await robot.move(arm, "shared_source", timeout_s=4)

    alloc_obs = await robot.grasp(
        arm, "shared_part", observation=await robot.inspect(arm, "allocation")
    )

    await robot.move(arm, "shared_target", timeout_s=4)

    await robot.release(arm, "shared_part", "shared_target")

    await robot.move(arm, depart_pose, timeout_s=4)

    _ = alloc_obs_id
    _ = alloc_obs


async def _unselected_branch(robot: Robot, arm: str) -> None:
    await _inspect_allocation(robot, arm)


async def _worker_a(robot: Robot) -> None:
    await _inspect_allocation(robot, "LEFT")
    await _inspect_allocation(robot, "RIGHT")

    await _selected_transport(robot, "LEFT", "left_home", "left_depart")
    await _unselected_branch(robot, "RIGHT")


async def _worker_b(robot: Robot) -> None:
    left_task = asyncio.create_task(_inspect_allocation(robot, "LEFT"))
    right_task = asyncio.create_task(_inspect_allocation(robot, "RIGHT"))
    await asyncio.gather(left_task, right_task)

    await _selected_transport(robot, "LEFT", "left_home", "left_depart")
    await _unselected_branch(robot, "RIGHT")


async def run_task(robot: Robot) -> None:
    await _worker_a(robot)
    await _worker_b(robot)
