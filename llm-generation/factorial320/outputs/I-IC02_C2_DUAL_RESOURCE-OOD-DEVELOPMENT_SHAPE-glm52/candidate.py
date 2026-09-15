import asyncio
from bridge_robot_api import Robot


async def _worker(robot: Robot, arm: str, part: str, source: str, target: str,
                  home: str, depart: str, fixture_rcpt, tool_rcpt) -> None:
    await robot.move(arm, source, receipt=fixture_rcpt)
    await robot.grasp(arm, part)
    await robot.move(arm, target, receipt=tool_rcpt)
    await robot.release(arm, target)
    await robot.move(arm, depart)


async def _run_lane(robot: Robot, arm: str, part: str, source: str, target: str,
                    home: str, depart: str) -> None:
    fixture_rcpt = None
    tool_rcpt = None
    try:
        fixture_rcpt = await robot.acquire(arm, "fixture", 5)
        tool_rcpt = await robot.acquire(arm, "tool", 5)
        await _worker(robot, arm, part, source, target, home, depart,
                      fixture_rcpt, tool_rcpt)
    finally:
        if tool_rcpt is not None:
            await robot.release_resource(arm, "tool")
        if fixture_rcpt is not None:
            await robot.release_resource(arm, "fixture")


async def _consumer(robot: Robot, gate_rcpt) -> None:
    await _run_lane(robot, "LEFT", "left_part", "left_source", "left_target",
                    "left_home", "left_depart")
    await _run_lane(robot, "RIGHT", "right_part", "right_source", "right_target",
                    "right_home", "right_depart")
    robot.clear_event("rq2_gate", expected_version=gate_rcpt.version)


async def _producer(robot: Robot) -> None:
    robot.signal("rq2_gate")


async def run_task(robot: Robot) -> None:
    for _ in range(1):
        gate_rcpt = robot.signal("rq2_gate")
        await asyncio.gather(_producer(robot), _consumer(robot, gate_rcpt))
