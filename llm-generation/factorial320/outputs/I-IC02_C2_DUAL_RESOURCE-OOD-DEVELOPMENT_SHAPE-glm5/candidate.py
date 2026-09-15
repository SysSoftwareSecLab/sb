import asyncio
import traceback


async def run_task(robot):
    """IC02_C2_DUAL_RESOURCE-OOD-DEVELOPMENT_SHAPE (variant A, SERIAL).

    Structure: FOR -> IF -> PAR_JOIN.
      - FOR: two serial worker iterations (LEFT lane, then RIGHT lane).
      - IF: inside each iteration, concurrently join an rq2_gate producer
            and a consumer. The consumer waits the exact active receipt,
            executes the complete inherited mission, then clears that version.
      - PAR_JOIN: asyncio.gather(producer, consumer).

    Mission per arm: acquire fixture then tool, carry the corresponding part
    to target while owning both, release and depart, then release tool and
    fixture. try/finally releases every successfully acquired controller on
    acquisition timeout.
    """

    async def worker(arm, part, source, target, depart):
        # PAR_JOIN: producer signals rq2_gate; consumer waits the exact active
        # receipt, runs the mission, then clears that version.
        async def producer():
            robot.signal("rq2_gate", part)

        async def consumer():
            receipt = await robot.wait_event("rq2_gate", 5)
            # IF contains the join and the consumer itself has no mission guard.
            await _mission(robot, arm, part, source, target, depart)
            robot.clear_event("rq2_gate", expected_version=receipt.version)

        await asyncio.gather(producer(), consumer())

    await worker("LEFT", "left_part", "left_home", "left_target", "left_depart")
    await worker("RIGHT", "right_part", "right_home", "right_target", "right_depart")


async def _mission(robot, arm, part, source, target, depart):
    fixture_owned = False
    tool_owned = False
    try:
        # Acquire fixture then tool (required order).
        await robot.acquire(arm, "fixture", 5)
        fixture_owned = True
        await robot.acquire(arm, "tool", 5)
        tool_owned = True

        # Approach from declared start_pose and immediately grasp.
        await robot.move(arm, source)
        await robot.grasp(arm, part)

        # Carry the part to target while owning both controllers.
        await robot.move(arm, target)

        # Release at the named support zone, then immediately depart.
        await robot.release(arm, part, target)
        await robot.move(arm, depart)

        # Release tool then fixture (reverse order), both OFF and unowned.
        if tool_owned:
            await robot.release_resource(arm, "tool")
            tool_owned = False
        if fixture_owned:
            await robot.release_resource(arm, "fixture")
            fixture_owned = False
    except Exception:
        # try/finally handles cleanup; re-raise after releasing controllers.
        raise
    finally:
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
