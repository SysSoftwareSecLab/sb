import asyncio
from bridge_robot_api import Robot


async def _worker_a(robot: Robot) -> None:
    """Worker A: runs candidate LEFT then RIGHT serially."""
    # Both workers independently inspect allocation once before choosing branch.
    left_alloc = await robot.inspect("LEFT", "allocation")
    right_alloc = await robot.inspect("RIGHT", "allocation")

    selected = left_alloc.value.get("selected_arm")
    item = left_alloc.value.get("item_id")

    if selected == "LEFT":
        await _transport(robot, "LEFT", item, left_alloc)
    elif selected == "RIGHT":
        await _transport(robot, "RIGHT", item, right_alloc)


async def _worker_b(robot: Robot) -> None:
    """Worker B: gathers candidates concurrently."""
    left_task = asyncio.create_task(robot.inspect("LEFT", "allocation"))
    right_task = asyncio.create_task(robot.inspect("RIGHT", "allocation"))
    left_alloc = await left_task
    right_alloc = await right_task

    selected = left_alloc.value.get("selected_arm")
    item = left_alloc.value.get("item_id")

    if selected == "LEFT":
        await _transport(robot, "LEFT", item, left_alloc)
    elif selected == "RIGHT":
        await _transport(robot, "RIGHT", item, right_alloc)


async def _transport(robot: Robot, arm: str, item: str, observation) -> None:
    """Selected arm: approach, grasp with current allocation observation,
    transport to target, release, and immediately depart."""
    home = f"{arm.lower()}_home"
    depart = f"{arm.lower()}_depart"

    # Approach: start_pose -> interaction_pose, then immediately grasp.
    await robot.move(arm, "shared_source")
    grasp_obs = await robot.grasp(arm, item, observation=observation)

    # Carry transport to target.
    await robot.move(arm, "shared_target")

    # Release at target support zone, then immediately depart.
    await robot.release(arm, item, "shared_target")
    await robot.move(arm, depart)


async def run_task(robot: Robot) -> None:
    """Implement DEPENDENCY_DISTANCE=LONG, layout=L0 structure.

    Two symmetric worker candidates inspect an allocation record for one
    shared payload. Exactly the selected worker may approach and transport
    it; the other remains at home. Worker A runs candidates serially;
    Worker B gathers them concurrently. Both perform the same inspections
    and one selected transport.
    """
    await asyncio.gather(_worker_a(robot), _worker_b(robot))
