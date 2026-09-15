import asyncio
from bridge_robot_api import Robot


async def _inspect_allocation(robot: Robot, arm: str):
    return await robot.inspect(arm, "allocation")


async def _selected_transport(robot: Robot, arm: str, allocation_obs):
    await robot.move(arm, "shared_source")
    await robot.grasp(arm, "shared_part", observation=allocation_obs)
    await robot.move(arm, "shared_target")
    await robot.release(arm, "shared_part", "shared_target")
    await robot.move(arm, "left_depart" if arm == "LEFT" else "right_home")


async def _worker_candidate(robot: Robot, arm: str):
    obs = await _inspect_allocation(robot, arm)
    selected = obs.value.get("selected_arm") if obs and obs.value else None
    if selected == arm:
        await _selected_transport(robot, arm, obs)


async def _gap_checks(robot: Robot):
    for i in range(3):
        rid = f"rq2_gap_{i}"
        await robot.acquire("LEFT", rid, 5)
        await robot.release_resource("LEFT", rid)


async def _inherited_mission(robot: Robot):
    a = asyncio.create_task(_worker_candidate(robot, "LEFT"))
    b = asyncio.create_task(_worker_candidate(robot, "RIGHT"))
    await asyncio.gather(a, b)


async def run_task(robot: Robot):
    await _gap_checks(robot)
    gate_receipt = robot.signal("rq2_gate")
    await robot.wait_event("rq2_gate", 5)
    await _inherited_mission(robot)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
