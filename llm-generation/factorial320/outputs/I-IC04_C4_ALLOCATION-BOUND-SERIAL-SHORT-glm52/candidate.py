import asyncio
from bridge_robot_api import Robot


async def _inspect_allocation(robot: Robot, arm: str):
    return await robot.inspect(arm, "allocation")


async def _selected_transport(robot: Robot, arm: str, alloc_obs):
    home_pose = f"{arm.lower()}_home"
    depart_pose = f"{arm.lower()}_depart"

    await robot.move(arm, "shared_source")
    grasp_obs = await robot.grasp(arm, "shared_part", observation=alloc_obs)
    await robot.move(arm, "shared_target")
    await robot.release(arm, "shared_part", "shared_target")
    await robot.move(arm, depart_pose)
    return grasp_obs


async def _gap_checks(robot: Robot):
    for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", rid, 5)
        await robot.release_resource("LEFT", rid)


async def _candidate(robot: Robot, arm: str, alloc_obs):
    selected = alloc_obs.value.get("selected_arm") == arm
    if selected:
        await _selected_transport(robot, arm, alloc_obs)
    else:
        # Unselected arm makes no move/grasp/release call; remains at home.
        return


async def _worker_a(robot: Robot):
    left_alloc = await _inspect_allocation(robot, "LEFT")
    await _candidate(robot, "LEFT", left_alloc)

    right_alloc = await _inspect_allocation(robot, "RIGHT")
    await _candidate(robot, "RIGHT", right_alloc)


async def _worker_b(robot: Robot):
    left_alloc = await _inspect_allocation(robot, "LEFT")
    right_alloc = await _inspect_allocation(robot, "RIGHT")

    left_task = asyncio.create_task(_candidate(robot, "LEFT", left_alloc))
    right_task = asyncio.create_task(_candidate(robot, "RIGHT", right_alloc))
    await asyncio.gather(left_task, right_task)


async def run_task(robot: Robot):
    # Complete all three rq2_gap resource checks before signalling rq2_gate.
    await _gap_checks(robot)

    # Signal rq2_gate exactly once.
    gate_receipt = robot.signal("rq2_gate")

    # Wait its exact active receipt exactly once, immediately after the signal.
    waited = await robot.wait_event("rq2_gate", 5)
    # Use the exact active receipt returned by wait_event for clearing later.
    clear_version = waited.version

    # Keep rq2_gate active while executing the complete inherited dual-arm mission.
    # Use serial scheduling for the inherited dual-arm mission.
    await _worker_a(robot)
    await _worker_b(robot)

    # Clear rq2_gate only after the mission, using the exact waited version.
    robot.clear_event("rq2_gate", expected_version=clear_version)
