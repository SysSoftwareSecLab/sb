import asyncio
from bridge_robot_api import Robot


async def _inspect_allocation(robot: Robot, arm: str):
    return await robot.inspect(arm, "allocation")


async def _selected_transport(robot: Robot, arm: str, home_pose: str, depart_pose: str, obs):
    await robot.move(arm, "shared_source")
    await robot.grasp(arm, "shared_part", observation=obs)
    await robot.move(arm, "shared_target")
    await robot.release(arm, "shared_part", "shared_target")
    await robot.move(arm, depart_pose)


async def _left_branch(robot: Robot, obs):
    await _selected_transport(robot, "LEFT", "left_home", "left_depart", obs)


async def _right_branch(robot: Robot, obs):
    await _selected_transport(robot, "RIGHT", "right_home", "right_depart", obs)


async def _consumer_mission(robot: Robot, receipt):
    left_obs = await _inspect_allocation(robot, "LEFT")
    right_obs = await _inspect_allocation(robot, "RIGHT")

    selected = None
    if left_obs.value.get("selected_arm") == "LEFT":
        selected = "LEFT"
    elif right_obs.value.get("selected_arm") == "RIGHT":
        selected = "RIGHT"

    if selected == "LEFT":
        await _left_branch(robot, left_obs)
    elif selected == "RIGHT":
        await _right_branch(robot, right_obs)

    await robot.move("LEFT", "left_depart", receipt=receipt)
    robot.clear_event("rq2_gate", expected_version=receipt.version)


async def run_task(robot: Robot):
    for _ in range(1):
        receipt = robot.signal("rq2_gate", item_id="shared_part")

        async def producer():
            await robot.wait_event("rq2_gate", 5)

        async def consumer():
            await _consumer_mission(robot, receipt)

        await asyncio.gather(producer(), consumer())
