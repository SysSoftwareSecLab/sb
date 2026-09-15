import asyncio
from bridge_robot_api import MotionFault

FIXTURE = "fixture"
TOOL = "tool"


async def _worker(robot, arm, home, source, target, depart, part):
    acquired = []
    try:
        await robot.acquire(arm, FIXTURE, 120)
        acquired.append(FIXTURE)
        await robot.acquire(arm, TOOL, 120)
        acquired.append(TOOL)

        await robot.move(arm, source)
        await robot.grasp(arm, part)
        await robot.move(arm, target)
        await robot.release(arm, part, target)
        await robot.move(arm, depart)

        await robot.release_resource(arm, TOOL)
        acquired.remove(TOOL)
        await robot.release_resource(arm, FIXTURE)
        acquired.remove(FIXTURE)
    finally:
        for resource in reversed(acquired):
            try:
                await robot.release_resource(arm, resource)
            except (Exception, MotionFault):
                pass


async def run_task(robot):
    left_task = asyncio.create_task(
        _worker(
            robot,
            "LEFT",
            "left_home",
            "left_source",
            "left_target",
            "left_depart",
            "left_part",
        )
    )
    right_task = asyncio.create_task(
        _worker(
            robot,
            "RIGHT",
            "right_home",
            "right_source",
            "right_target",
            "right_depart",
            "right_part",
        )
    )
    await asyncio.gather(left_task, right_task)
