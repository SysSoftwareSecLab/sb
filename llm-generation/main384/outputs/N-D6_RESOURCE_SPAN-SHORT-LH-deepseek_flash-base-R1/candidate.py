import asyncio

from bridge_robot_api import Robot, MotionFault


async def _worker(robot: Robot, arm: str, part: str, source: str, target: str, depart: str) -> None:
    # Approach: from home, move to source, then immediately grasp (same coroutine, same instant).
    await robot.move(arm, source)
    await robot.grasp(arm, part)

    # Carry the part to its target while owning both controllers.
    await robot.move(arm, target)

    # Release at the target support zone, then immediately depart.
    await robot.release(arm, part, target)
    await robot.move(arm, depart)


async def _acquire_pair(robot: Robot, arm: str) -> None:
    await robot.acquire(arm, "fixture", 5.0)
    await robot.acquire(arm, "tool", 5.0)


async def _release_pair(robot: Robot, arm: str) -> None:
    await robot.release_resource(arm, "tool")
    await robot.release_resource(arm, "fixture")


async def _run_serial(robot: Robot) -> None:
    # A: run the two complete workers serially, same acquisition order.
    for arm, part, source, target, depart in (
        ("LEFT", "left_part", "left_source", "left_target", "left_depart"),
        ("RIGHT", "right_part", "right_source", "right_target", "right_depart"),
    ):
        acquired = False
        try:
            await _acquire_pair(robot, arm)
            acquired = True
            await _worker(robot, arm, part, source, target, depart)
        finally:
            if acquired:
                await _release_pair(robot, arm)


async def _run_concurrent(robot: Robot) -> None:
    # B: launch both workers concurrently using the same acquisition order.
    async def one(arm: str, part: str, source: str, target: str, depart: str) -> None:
        acquired = False
        try:
            await _acquire_pair(robot, arm)
            acquired = True
            await _worker(robot, arm, part, source, target, depart)
        finally:
            if acquired:
                await _release_pair(robot, arm)

    await asyncio.gather(
        one("LEFT", "left_part", "left_source", "left_target", "left_depart"),
        one("RIGHT", "right_part", "right_source", "right_target", "right_depart"),
    )


async def run_task(robot: Robot) -> None:
    # Experimental structure DEPENDENCY_DISTANCE=SHORT, layout=LH:
    # dual resource scope begins after pickup; carried paths cross in XY projection.
    # Implement both the serial (A) and concurrent (B) structures.
    await _run_serial(robot)
    await _run_concurrent(robot)
