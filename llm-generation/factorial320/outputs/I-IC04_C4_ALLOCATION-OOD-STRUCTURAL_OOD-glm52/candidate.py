import asyncio
from bridge_robot_api import Robot


async def _inspect_allocation(robot: Robot, arm: str):
    return await robot.inspect(arm, "allocation")


async def _selected_transport(robot: Robot, arm: str, alloc_obs):
    if arm == "LEFT":
        start_pose = "left_home"
        depart_pose = "left_depart"
    else:
        start_pose = "right_home"
        depart_pose = "right_depart"

    await robot.move(arm, start_pose)
    await robot.grasp(arm, "shared_part", observation=alloc_obs)
    await robot.move(arm, "shared_target")
    await robot.release(arm, "shared_part", "shared_target")
    await robot.move(arm, depart_pose)


async def _consumer_mission(robot: Robot, receipt):
    left_obs = await _inspect_allocation(robot, "LEFT")
    right_obs = await _inspect_allocation(robot, "RIGHT")

    selected = left_obs.value.get("selected_arm", "LEFT")
    if selected == "LEFT":
        await _selected_transport(robot, "LEFT", left_obs)
        await robot.move("RIGHT", "right_home")
    else:
        await _selected_transport(robot, "RIGHT", right_obs)
        await robot.move("LEFT", "left_depart")

    await robot.move(receipt=receipt, arm="LEFT", pose="left_depart")
    robot.clear_event("rq2_gate", expected_version=receipt.version)


async def run_task(robot: Robot):
    for _ in range(1):
        producer = asyncio.create_task(asyncio.to_thread(robot.signal, "rq2_gate", None))
        consumer = asyncio.create_task(_consumer_mission(robot, await producer))
        await consumer
