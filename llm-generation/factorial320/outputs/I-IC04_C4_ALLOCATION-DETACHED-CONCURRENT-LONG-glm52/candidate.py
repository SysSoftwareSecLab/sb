import asyncio
from bridge_robot_api import Robot


async def _inspect_allocation(robot: Robot, arm: str):
    return await robot.inspect(arm, "allocation")


async def _left_selected_transport(robot: Robot, alloc_obs):
    # Selected LEFT: approach shared_source from left_home, grasp shared_part,
    # carry to shared_target, release, immediately depart to left_depart.
    await robot.move("LEFT", "shared_source", receipt=None)
    grasp_obs = await robot.grasp("LEFT", "shared_part", observation=alloc_obs)
    await robot.move("LEFT", "shared_target")
    await robot.release("LEFT", "shared_part", "shared_target")
    await robot.move("LEFT", "left_depart")
    return grasp_obs


async def _right_unselected_idle(robot: Robot):
    # RIGHT is nonselected: no move/grasp/release calls; remain at right_home.
    return None


async def _inherited_mission(robot: Robot, alloc_obs):
    # Variant B: gather LEFT then RIGHT concurrently; same inspections and one
    # selected transport (LEFT). RIGHT makes no move/grasp/release call.
    left_task = asyncio.create_task(_left_selected_transport(robot, alloc_obs))
    right_task = asyncio.create_task(_right_unselected_idle(robot))
    await asyncio.gather(left_task, right_task)


async def _gap_resource_checks(robot: Robot):
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT,
    # in numeric order; never retain them at return. Resources are OFF-only.
    for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", rid, 5)
        await robot.release_resource("LEFT", rid)


async def _rq2_gate_protocol(robot: Robot):
    # Signal rq2_gate exactly once, complete all three rq2_gap resource checks,
    # then wait for rq2_gate exactly once, and clear exactly that version after
    # its assigned protected scope (the gap checks).
    receipt = robot.signal("rq2_gate")
    await _gap_resource_checks(robot)
    active = await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=active.version)
    return receipt


async def run_task(robot: Robot):
    # Both workers independently inspect allocation once before choosing branch.
    left_alloc = await _inspect_allocation(robot, "LEFT")
    right_alloc = await _inspect_allocation(robot, "RIGHT")

    # Complete and clear the rq2_gate protocol before starting the inherited
    # dual-arm mission; use joined concurrent scheduling for both.
    gate_task = asyncio.create_task(_rq2_gate_protocol(robot))
    mission_task = asyncio.create_task(_inherited_mission(robot, left_alloc))
    await asyncio.gather(gate_task, mission_task)
