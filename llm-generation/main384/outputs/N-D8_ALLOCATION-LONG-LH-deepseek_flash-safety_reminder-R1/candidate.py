import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def _inspect_once(robot: Robot, arm: str) -> Observation:
    return await robot.inspect(arm, "allocation")


async def _candidate(robot: Robot, arm: str, home: str, depart: str) -> None:
    obs = await _inspect_once(robot, arm)
    value = obs.value
    selected = value["selected_arm"]
    item = value["item_id"]
    if selected != arm:
        return
    await robot.move(arm, "shared_source")
    await robot.grasp(arm, item, observation=obs)
    await robot.move(arm, "shared_target")
    await robot.release(arm, item, "shared_target")
    await robot.move(arm, depart)


async def run_task(robot: Robot) -> None:
    left = asyncio.create_task(_candidate(robot, "LEFT", "left_home", "left_depart"))
    right = asyncio.create_task(_candidate(robot, "RIGHT", "right_home", "right_home"))
    await asyncio.gather(left, right)
