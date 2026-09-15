import asyncio

from bridge_robot_api import Robot


async def _gap_check(robot: Robot, resource_id: str) -> None:
    await robot.acquire("LEFT", resource_id, 5)
    try:
        pass
    finally:
        await robot.release_resource("LEFT", resource_id)


async def _gate_protocol(robot: Robot) -> None:
    await _gap_check(robot, "rq2_gap_0")
    await _gap_check(robot, "rq2_gap_1")
    await _gap_check(robot, "rq2_gap_2")

    receipt = robot.signal("rq2_gate")
    try:
        await robot.wait_event("rq2_gate", 5)
    finally:
        robot.clear_event("rq2_gate", expected_version=receipt.version)


async def _worker(robot: Robot, arm: str, home: str, source: str,
                  target: str, depart: str, part: str) -> None:
    await robot.move(arm, source)
    await robot.grasp(arm, part)
    await robot.acquire(arm, "fixture", 5)
    try:
        await robot.acquire(arm, "tool", 5)
        try:
            await robot.move(arm, target)
            await robot.release(arm, part, target)
            await robot.move(arm, depart)
        finally:
            await robot.release_resource(arm, "tool")
    finally:
        await robot.release_resource(arm, "fixture")


async def run_task(robot: Robot) -> None:
    await _gate_protocol(robot)

    left_task = asyncio.create_task(
        _worker(robot, "LEFT", "left_home", "left_source",
                "left_target", "left_depart", "left_part")
    )
    right_task = asyncio.create_task(
        _worker(robot, "RIGHT", "right_home", "right_source",
                "right_target", "right_depart", "right_part")
    )

    try:
        await asyncio.gather(left_task, right_task)
    except BaseException:
        left_task.cancel()
        right_task.cancel()
        try:
            await asyncio.gather(left_task, right_task, return_exceptions=True)
        except BaseException:
            pass
        raise
