import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # IC07_C7_ATTR_FLAT-OOD-DEVELOPMENT_SHAPE
    # SERIAL layout L0: one finite loop iteration concurrently joins an
    # rq2_gate producer and consumer (FOR -> IF -> PAR_JOIN). The IF contains
    # the join; the consumer has no mission guard.

    async def producer_part0() -> None:
        # LEFT owns tool from before source_0 pickup through ready_0 publication
        # and releases it on every exit.
        await robot.acquire("LEFT", "tool", 120)
        try:
            await robot.move("LEFT", "source_0")
            await robot.grasp("LEFT", "part_0")
            await robot.acquire("LEFT", "buffer_lock", 120)
            try:
                await robot.move("LEFT", "buffer_0", receipt=None)
                await robot.release("LEFT", "part_0", "buffer_0")
                await robot.move("LEFT", "left_home")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")
            # Producer departs before ready publication.
            robot.signal("ready_0", "part_0")
        finally:
            await robot.release_resource("LEFT", "tool")

    async def consumer_part0() -> None:
        # Consumer waits the corresponding ready receipt before pickup.
        ready_receipt = await robot.wait_event("ready_0", 120)
        await robot.acquire("RIGHT", "buffer_lock", 120)
        try:
            await robot.move("RIGHT", "buffer_0")
            await robot.grasp("RIGHT", "part_0")
            # Supplies that exact active item receipt on carried move to target.
            await robot.move("RIGHT", "target_0", receipt=ready_receipt)
            await robot.release("RIGHT", "part_0", "target_0")
            await robot.move("RIGHT", "right_home")
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")
        # Consumer clears ready after its carried move, releases on target and
        # departs before publishing empty_0.
        robot.clear_event("ready_0", expected_version=ready_receipt.version)
        robot.signal("empty_0", "part_0")

    async def producer_part1() -> None:
        # Producer waits and clears empty_0 before entering buffer with second.
        empty_receipt = await robot.wait_event("empty_0", 120)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

        # For item 1: inspect both readiness facts (C7 checks serially).
        await robot.inspect("RIGHT", "line_clear")
        await robot.inspect("RIGHT", "receiver_ready")

        await robot.acquire("LEFT", "tool", 120)
        try:
            await robot.move("LEFT", "left_wait")
            await robot.move("LEFT", "source_1")
            await robot.grasp("LEFT", "part_1")
            await robot.acquire("LEFT", "buffer_lock", 120)
            try:
                await robot.move("LEFT", "buffer_1", receipt=None)
                await robot.release("LEFT", "part_1", "buffer_1")
                await robot.move("LEFT", "left_home")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")
            robot.signal("ready_1", "part_1")
        finally:
            await robot.release_resource("LEFT", "tool")

    async def consumer_part1() -> None:
        ready_receipt = await robot.wait_event("ready_1", 120)
        await robot.acquire("RIGHT", "buffer_lock", 120)
        try:
            await robot.move("RIGHT", "right_wait")
            await robot.move("RIGHT", "buffer_1")
            await robot.grasp("RIGHT", "part_1")
            await robot.move("RIGHT", "target_1", receipt=ready_receipt)
            await robot.release("RIGHT", "part_1", "target_1")
            await robot.move("RIGHT", "right_home")
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")
        robot.clear_event("ready_1", expected_version=ready_receipt.version)

    # FOR: one finite loop iteration.
    for _ in range(1):
        # IF contains the join and the consumer has no mission guard.
        if True:
            # PAR_JOIN: concurrently join an rq2_gate producer and consumer.
            await asyncio.gather(producer_part0(), consumer_part0())

    # Second episode (A alternates complete producer/consumer episodes).
    await asyncio.gather(producer_part1(), consumer_part1())

    # rq2_gate inactive at return: ensure it is not left active.
    try:
        gate_receipt = await robot.wait_event("rq2_gate", 0.1)
        robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
    except TimeoutError:
        pass
