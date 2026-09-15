import asyncio
import traceback

from bridge_robot_api import MotionFault


async def _acquire_chain(robot, arm, resources, timeout_s):
    acquired = []
    try:
        for rid in resources:
            await robot.acquire(arm, rid, timeout_s)
            acquired.append(rid)
        return acquired
    except Exception:
        for rid in reversed(acquired):
            try:
                await robot.release_resource(arm, rid)
            except Exception:
                pass
        raise


async def _release_all(robot, arm, resources):
    for rid in reversed(resources):
        try:
            await robot.release_resource(arm, rid)
        except Exception:
            pass


async def _worker(robot, arm, part, start, source, target, depart,
                  resources, acquire_timeout):
    acquired = []
    try:
        acquired = await _acquire_chain(robot, arm, resources, acquire_timeout)
        await robot.move(arm, source)
        await robot.grasp(arm, part)
        await robot.move(arm, target)
        await robot.release(arm, part, target)
        await robot.move(arm, depart)
    finally:
        await _release_all(robot, arm, acquired)


async def _worker_left(robot, acquire_timeout):
    return await _worker(
        robot, "LEFT", "left_part",
        "left_home", "left_source", "left_target", "left_depart",
        ["fixture", "tool"], acquire_timeout,
    )


async def _worker_right(robot, acquire_timeout):
    return await _worker(
        robot, "RIGHT", "right_part",
        "right_home", "right_source", "right_target", "right_depart",
        ["fixture", "tool"], acquire_timeout,
    )


async def run_task(robot):
    acquire_timeout = 120

    # Variant B: launch both workers concurrently using the same acquisition order.
    left = asyncio.create_task(_worker_left(robot, acquire_timeout))
    right = asyncio.create_task(_worker_right(robot, acquire_timeout))
    try:
        await asyncio.gather(left, right)
    except MotionFault:
        await _release_all(robot, "LEFT", ["fixture", "tool"])
        await _release_all(robot, "RIGHT", ["fixture", "tool"])
        raise
    except Exception:
        # Best-effort cleanup of any resources that may have been acquired.
        await _release_all(robot, "LEFT", ["fixture", "tool"])
        await _release_all(robot, "RIGHT", ["fixture", "tool"])
        raise
