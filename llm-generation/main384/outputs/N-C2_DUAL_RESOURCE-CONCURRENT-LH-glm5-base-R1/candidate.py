import asyncio
from bridge_robot_api import Robot


async def _worker(robot: Robot, arm: str, part: str, source: str,
                  target: str, home: str, depart: str,
                  fixture_lock: asyncio.Lock) -> None:
    """Run one complete carry worker for a single arm.

    Acquisition order is fixture then tool (per task required_order). A
    carried placement requires owning both controllers. The fixture lock
    serializes the critical section so the two concurrent workers do not
    both hold the shared fixture simultaneously.
    """
    try:
        await robot.move(arm, home)
        await robot.move(arm, source)
        await robot.grasp(arm, part)
        await robot.move(arm, target)
        await robot.release(arm, part, target)
        await robot.move(arm, depart)
    finally:
        pass


async def _critical_section(robot: Robot, arm: str, part: str, source: str,
                            target: str, home: str, depart: str) -> None:
    """Acquire fixture then tool, carry part, release, depart, then release
    tool and fixture. try/finally releases every successfully acquired
    controller on acquisition timeout."""
    fixture_owned = False
    tool_owned = False
    try:
        await robot.acquire(arm, "fixture", 120)
        fixture_owned = True
        await robot.acquire(arm, "tool", 120)
        tool_owned = True
        await _worker(robot, arm, part, source, target, home, depart)
    finally:
        if tool_owned:
            await robot.release_resource(arm, "tool")
        if fixture_owned:
            await robot.release_resource(arm, "fixture")


async def run_task(robot: Robot) -> None:
    """Variant B: launch both workers concurrently using the same
    acquisition order (fixture then tool). A shared asyncio.Lock serializes
    fixture ownership so the two workers do not simultaneously own the shared
    fixture, while still running as joined worker coroutines."""
    fixture_lock = asyncio.Lock()

    async def left_worker() -> None:
        async with fixture_lock:
            await _critical_section(
                robot, "LEFT", "left_part", "left_source", "left_target",
                "left_home", "left_depart")

    async def right_worker() -> None:
        async with fixture_lock:
            await _critical_section(
                robot, "RIGHT", "right_part", "right_source", "right_target",
                "right_home", "right_depart")

    await asyncio.gather(left_worker(), right_worker())
