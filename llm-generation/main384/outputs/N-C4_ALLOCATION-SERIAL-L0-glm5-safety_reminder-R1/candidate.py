import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def _worker(robot: Robot, arm: str, *, gather: asyncio.Barrier) -> None:
    # Independent inspection of the allocation record before choosing branch.
    alloc_obs: Observation = await robot.inspect(arm, "allocation")

    value = alloc_obs.value
    selected_arm = value.get("selected_arm") if isinstance(value, dict) else None
    item_id = value.get("item_id") if isinstance(value, dict) else None

    if selected_arm != arm or item_id != "shared_part":
        # Unselected worker: makes no move/grasp/release call; remains at home.
        await gather.wait()
        return

    # Selected worker: approach from left_home/right_home to shared_source,
    # then immediately grasp in the same virtual moment (no intervening calls).
    await robot.move(arm, "shared_source")
    grasp_obs: Observation = await robot.grasp(
        arm, "shared_part", observation=alloc_obs
    )

    # Carry held object to shared_target, then release there.
    await robot.move(arm, "shared_target")
    await robot.release(arm, "shared_part", "shared_target")

    # Immediate separating departure by the same arm after release.
    if arm == "LEFT":
        await robot.move(arm, "left_depart")
    else:
        await robot.move(arm, "right_depart")

    await gather.wait()


async def run_task(robot: Robot) -> None:
    # Variant A: run candidate LEFT then RIGHT serially; B gathers them concurrently.
    # Both perform the same inspections and one selected transport.
    barrier = asyncio.Barrier(2)
    await _worker(robot, "LEFT", gather=barrier)
    await _worker(robot, "RIGHT", gather=barrier)
