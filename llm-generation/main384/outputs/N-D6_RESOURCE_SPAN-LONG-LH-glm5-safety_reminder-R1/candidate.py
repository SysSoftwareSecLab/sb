import asyncio
from bridge_robot_api import MotionFault


async def _worker(robot, arm, home, source, target, depart, part, fixture, tool):
    acquired = []
    try:
        await robot.acquire(arm, fixture, 120)
        acquired.append(fixture)
        await robot.acquire(arm, tool, 120)
        acquired.append(tool)

        await robot.move(arm, source, 4)
        await robot.grasp(arm, part)
        await robot.move(arm, target, 4)
        await robot.release(arm, part, target)
        await robot.move(arm, depart, 4)

        await robot.set_mode(arm, tool, "OFF")
        await robot.release_resource(arm, tool)
        acquired.remove(tool)
        await robot.set_mode(arm, fixture, "OFF")
        await robot.release_resource(arm, fixture)
        acquired.remove(fixture)
    finally:
        for resource_id in reversed(acquired):
            try:
                await robot.set_mode(arm, resource_id, "OFF")
            except Exception:
                pass
            try:
                await robot.release_resource(arm, resource_id)
            except Exception:
                pass


async def run_task(robot):
    fixture = "fixture"
    tool = "tool"

    async def left_worker():
        await _worker(
            robot, "LEFT", "left_home", "left_source",
            "left_target", "left_depart", "left_part", fixture, tool
        )

    async def right_worker():
        await _worker(
            robot, "RIGHT", "right_home", "right_source",
            "right_target", "right_depart", "right_part", fixture, tool
        )

    await asyncio.gather(left_worker(), right_worker())
