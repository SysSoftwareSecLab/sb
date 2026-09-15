from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def _worker(robot: Robot, arm: str, part: str, source: str, target: str, depart: str) -> None:
    fixture_owned = False
    tool_owned = False
    try:
        await robot.acquire(arm, "fixture", 5.0)
        fixture_owned = True
        await robot.acquire(arm, "tool", 5.0)
        tool_owned = True

        await robot.move(arm, source)
        await robot.grasp(arm, part)
        await robot.move(arm, target)
        await robot.release(arm, part, target)
        await robot.move(arm, depart)
    finally:
        if tool_owned:
            await robot.release_resource(arm, "tool")
        if fixture_owned:
            await robot.release_resource(arm, "fixture")


async def run_task(robot: Robot) -> None:
    await _worker(robot, "LEFT", "left_part", "left_source", "left_target", "left_depart")
    await _worker(robot, "RIGHT", "right_part", "right_source", "right_target", "right_depart")
