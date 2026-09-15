from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def _worker(robot: Robot, arm: str, home_pose: str, depart_pose: str) -> None:
    obs = await robot.inspect(arm, "allocation")
    selected = obs.value["selected_arm"]
    if selected != arm:
        return
    await robot.move(arm, "shared_source")
    await robot.grasp(arm, "shared_part", observation=obs)
    await robot.move(arm, "shared_target")
    await robot.release(arm, "shared_part", "shared_target")
    await robot.move(arm, depart_pose)


async def run_task(robot: Robot) -> None:
    await _worker(robot, "LEFT", "left_home", "left_depart")
    await _worker(robot, "RIGHT", "right_home", "right_home")
