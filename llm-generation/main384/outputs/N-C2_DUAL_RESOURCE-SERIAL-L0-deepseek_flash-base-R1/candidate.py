from bridge_robot_api import Robot, MotionFault


async def _worker(robot: Robot, arm: str, part: str, source: str, target: str, depart: str) -> None:
    fixture_owned = False
    tool_owned = False
    holding = False
    try:
        await robot.acquire(arm, "fixture", 5.0)
        fixture_owned = True
        await robot.acquire(arm, "tool", 5.0)
        tool_owned = True

        await robot.move(arm, source)
        await robot.grasp(arm, part)
        holding = True

        await robot.move(arm, target)
        await robot.release(arm, part, target)
        holding = False

        await robot.move(arm, depart)
    finally:
        if holding:
            try:
                await robot.release(arm, part, target)
            except Exception:
                pass
        if tool_owned:
            try:
                await robot.release_resource(arm, "tool")
            except Exception:
                pass
        if fixture_owned:
            try:
                await robot.release_resource(arm, "fixture")
            except Exception:
                pass


async def run_task(robot: Robot) -> None:
    # CONCURRENCY=SERIAL, layout=L0: run the two complete workers serially.
    await _worker(robot, "LEFT", "left_part", "left_source", "left_target", "left_depart")
    await _worker(robot, "RIGHT", "right_part", "right_source", "right_target", "right_depart")
