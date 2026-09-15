import asyncio
from bridge_robot_api import MotionFault


async def run_task(robot):
    """C2_DUAL_RESOURCE-SERIAL-LH, variant A.

    Stated structure: run the two complete workers serially (LEFT then RIGHT),
    with the same acquisition order (fixture then tool) for each worker.
    """

    async def worker(arm, part, source, target, depart, home):
        # Acquire fixture then tool; try/finally releases every successfully
        # acquired controller on acquisition timeout.
        acquired = []
        try:
            await robot.acquire(arm, "fixture", 120)
            acquired.append("fixture")
            await robot.acquire(arm, "tool", 120)
            acquired.append("tool")

            # Approach from declared start_pose to interaction_pose, then
            # immediately grasp in the same virtual moment.
            await robot.move(arm, source)
            await robot.grasp(arm, part)

            # Carry the corresponding part to target while owning both.
            await robot.move(arm, target)

            # Release at the named support_zone, then immediately depart.
            await robot.release(arm, part, target)
            await robot.move(arm, depart)
        finally:
            # Release tool then fixture (reverse order of acquisition).
            for resource_id in reversed(acquired):
                # set_mode OFF is required before release_resource for a
                # non-OFF mode; resources start and stay OFF here, so no
                # profile event is needed. release_resource requires OFF.
                await robot.set_mode(arm, resource_id, "OFF")
                await robot.release_resource(arm, resource_id)

    # Variant A: SERIAL. Run LEFT worker to completion, then RIGHT worker.
    await worker(
        "LEFT",
        "left_part",
        "left_source",
        "left_target",
        "left_depart",
        "left_home",
    )
    await worker(
        "RIGHT",
        "right_part",
        "right_source",
        "right_target",
        "right_depart",
        "right_home",
    )
