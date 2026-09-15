from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def _worker(robot, arm, part, source, target, depart, fixture, tool):
    acquired = []
    try:
        r1 = await robot.acquire(arm, fixture, 5.0)
        acquired.append(fixture)
        r2 = await robot.acquire(arm, tool, 5.0)
        acquired.append(tool)

        await robot.move(arm, source)
        await robot.grasp(arm, part)
        await robot.move(arm, target)
        await robot.release(arm, part, target)
        await robot.move(arm, depart)
    finally:
        for res in reversed(acquired):
            try:
                await robot.release_resource(arm, res)
            except Exception:
                pass


async def run_task(robot: Robot):
    await _worker(robot, "LEFT", "left_part", "left_source", "left_target", "left_depart", "fixture", "tool")
    await _worker(robot, "RIGHT", "right_part", "right_source", "right_target", "right_depart", "fixture", "tool")
