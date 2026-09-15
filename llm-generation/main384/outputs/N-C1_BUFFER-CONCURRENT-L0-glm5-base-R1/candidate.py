import asyncio

async def run_task(robot):
    """C1_BUFFER-CONCURRENT-L0, variant B.

    Two parts cross a capacity-one buffer from LEFT producer to RIGHT consumer.
    A alternates complete producer/consumer episodes; B runs producer and
    consumer coroutines together.  This implementation is variant B: producer
    and consumer coroutines run concurrently, synchronized through the buffer
    lock and the ready/empty events.
    """

    # ---- Episode 0: part_0 source_0 -> buffer_0 -> target_0 ----
    # ---- Episode 1: part_1 source_1 -> buffer_1 -> target_1 ----

    async def producer_episode(part, source, buffer_pose, ready_event,
                               empty_event, first):
        """LEFT arm: pick part from source, place at buffer, depart, publish."""
        # Approach source from left_home and immediately grasp.
        await robot.move("LEFT", source)
        await robot.grasp("LEFT", part)

        # Acquire buffer lock for entry.
        await robot.acquire("LEFT", "buffer_lock", 5)

        # Carry to buffer.
        await robot.move("LEFT", buffer_pose, receipt=None)

        # Release onto buffer (support_zone is the buffer pose name).
        await robot.release("LEFT", part, buffer_pose)

        # Depart from buffer to left_home (immediate separating departure).
        await robot.move("LEFT", "left_home")

        # Release lock after departure.
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready event for consumer.
        ready_rcpt = robot.signal(ready_event, part)

        # For the second episode, wait for empty_0 before entering buffer.
        if not first:
            await robot.wait_event(empty_event, 30)
            # Clear empty_0 after waiting (producer clears empty_0).
            empty_rcpt = await robot.wait_event(empty_event, 0.1)
            robot.clear_event(empty_event, expected_version=empty_rcpt.version)

        return ready_rcpt

    async def consumer_episode(part, buffer_pose, target, ready_event,
                                empty_event, last):
        """RIGHT arm: wait ready, pick from buffer, carry to target, publish empty."""
        # Wait for producer's ready receipt.
        ready_rcpt = await robot.wait_event(ready_event, 30)

        # Acquire buffer lock for pickup.
        await robot.acquire("RIGHT", "buffer_lock", 5)

        # Approach buffer from right_home and immediately grasp.
        await robot.move("RIGHT", buffer_pose)
        await robot.grasp("RIGHT", part)

        # Carry to target, supplying the exact active item receipt.
        await robot.move("RIGHT", target, receipt=ready_rcpt)

        # Clear ready after carried move completes.
        robot.clear_event(ready_event, expected_version=ready_rcpt.version)

        # Release on target.
        await robot.release("RIGHT", part, target)

        # Depart to right_home.
        await robot.move("RIGHT", "right_home")

        # Release lock after departure.
        await robot.release_resource("RIGHT", "buffer_lock")

        # Publish empty_0.
        empty_rcpt = robot.signal(empty_event, part)

        # For the last episode, clear empty_0 after publishing.
        if last:
            robot.clear_event(empty_event, expected_version=empty_rcpt.version)

        return empty_rcpt

    async def episode_0():
        """Concurrent producer and consumer for part_0."""
        ready_rcpt_box = {}

        async def prod0():
            rcpt = await producer_episode(
                "part_0", "source_0", "buffer_0", "ready_0", "empty_0",
                first=True)
            ready_rcpt_box["rcpt"] = rcpt

        async def cons0():
            # Wait for ready receipt.
            ready_rcpt = await robot.wait_event("ready_0", 30)
            await robot.acquire("RIGHT", "buffer_lock", 5)
            await robot.move("RIGHT", "buffer_0")
            await robot.grasp("RIGHT", "part_0")
            await robot.move("RIGHT", "target_0", receipt=ready_rcpt)
            robot.clear_event("ready_0", expected_version=ready_rcpt.version)
            await robot.release("RIGHT", "part_0", "target_0")
            await robot.move("RIGHT", "right_home")
            await robot.release_resource("RIGHT", "buffer_lock")
            empty_rcpt = robot.signal("empty_0", "part_0")
            robot.clear_event("empty_0", expected_version=empty_rcpt.version)

        await asyncio.gather(prod0(), cons0())

    async def episode_1():
        """Concurrent producer and consumer for part_1."""
        async def prod1():
            # Wait for empty_0 before entering buffer with second part.
            await robot.wait_event("empty_0", 30)
            # Clear empty_0 (producer clears empty_0 before entering buffer).
            empty_rcpt = await robot.wait_event("empty_0", 0.1)
            robot.clear_event("empty_0", expected_version=empty_rcpt.version)

            # Move to left_wait first (approach start for source_1).
            await robot.move("LEFT", "left_wait")
            await robot.move("LEFT", "source_1")
            await robot.grasp("LEFT", "part_1")
            await robot.acquire("LEFT", "buffer_lock", 5)
            await robot.move("LEFT", "buffer_1", receipt=None)
            await robot.release("LEFT", "part_1", "buffer_1")
            await robot.move("LEFT", "left_home")
            await robot.release_resource("LEFT", "buffer_lock")
            robot.signal("ready_1", "part_1")

        async def cons1():
            ready_rcpt = await robot.wait_event("ready_1", 30)
            await robot.acquire("RIGHT", "buffer_lock", 5)
            await robot.move("RIGHT", "buffer_1")
            await robot.grasp("RIGHT", "part_1")
            await robot.move("RIGHT", "target_1", receipt=ready_rcpt)
            robot.clear_event("ready_1", expected_version=ready_rcpt.version)
            await robot.release("RIGHT", "part_1", "target_1")
            await robot.move("RIGHT", "right_home")
            await robot.release_resource("RIGHT", "buffer_lock")
            empty_rcpt = robot.signal("empty_0", "part_1")
            robot.clear_event("empty_0", expected_version=empty_rcpt.version)

        await asyncio.gather(prod1(), cons1())

    await episode_0()
    await episode_1()
