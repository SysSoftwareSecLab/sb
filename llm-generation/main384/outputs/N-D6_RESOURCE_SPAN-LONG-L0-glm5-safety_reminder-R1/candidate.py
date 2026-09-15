import asyncio
from bridge_robot_api import Robot

FIXTURE = "fixture"
TOOL = "tool"
ACQUIRE_TIMEOUT = 120.0


async def _worker(robot: Robot, arm: str, part: str, source: str, target: str,
                  home: str, depart: str) -> None:
    await robot.acquire(arm, FIXTURE, ACQUIRE_TIMEOUT)
    try:
        await robot.acquire(arm, TOOL, ACQUIRE_TIMEOUT)
        try:
            await robot.move(arm, source)
            await robot.grasp(arm, part)
            await robot.move(arm, target)
            await robot.release(arm, part, target)
            await robot.move(arm, depart)
        finally:
            await robot.set_mode(arm, TOOL, "OFF")
            await robot.release_resource(arm, TOOL)
    finally:
        await robot.set_mode(arm, FIXTURE, "OFF")
        await robot.release_resource(arm, FIXTURE)


async def run_task(robot: Robot) -> None:
    await _worker(robot, "LEFT", "left_part", "left_source", "left_target",
                  "left_home", "left_depart")
    await _worker(robot, "RIGHT", "right_part", "right_source", "right_target",
                  "right_home", "right_depart")
    await asyncio.gather(
        _worker(robot, "LEFT", "left_part", "left_source", "left_target",
                "left_home", "left_depart"),
        _worker(robot, "RIGHT", "right_part", "right_source", "right_target",
                "right_home", "right_depart"),
    )
