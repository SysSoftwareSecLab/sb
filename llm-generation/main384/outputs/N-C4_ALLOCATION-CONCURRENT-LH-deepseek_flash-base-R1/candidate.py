from __future__ import annotations

import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def _worker(robot: Robot, arm: str, other_arm: str, results: dict) -> None:
    # Each worker independently inspects the allocation fact once.
    obs = await robot.inspect(arm, "allocation")
    results[arm] = obs

    # Determine whether this arm is the selected one from its own observation.
    value = obs.value
    selected = None
    if isinstance(value, dict):
        selected = value.get("selected_arm")
    if selected != arm:
        # Unselected arm makes no move/grasp/release call.
        return

    # Selected arm: approach shared_source from its home pose, then grasp.
    # Approach must start from the declared start_pose and the same coroutine
    # must immediately call grasp with no intervening robot calls.
    if arm == "LEFT":
        await robot.move("LEFT", "left_home")
    else:
        await robot.move("RIGHT", "right_home")

    await robot.grasp(arm, "shared_part", observation=obs)

    # Transport to shared_target.
    await robot.move(arm, "shared_target")

    # Release at target, then immediately depart.
    await robot.release(arm, "shared_part", "shared_target")

    if arm == "LEFT":
        await robot.move("LEFT", "left_depart")
    else:
        await robot.move("RIGHT", "right_depart")


async def run_task(robot: Robot) -> None:
    results: dict = {}

    # Variant B: gather the two worker candidates concurrently.
    await asyncio.gather(
        _worker(robot, "LEFT", "RIGHT", results),
        _worker(robot, "RIGHT", "LEFT", results),
    )
