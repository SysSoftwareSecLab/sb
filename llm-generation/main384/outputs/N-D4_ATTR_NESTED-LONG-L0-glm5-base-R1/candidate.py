import asyncio

async def run_task(robot):
    """D4_ATTR_NESTED-LONG-L0: two parts cross a capacity-one buffer.

    A = LEFT producer; B = RIGHT consumer.  B runs producer and consumer
    coroutines together.  For the second item, D4 joins the two checks
    (line_clear with LEFT, receiver_ready with RIGHT) with asyncio.gather
    inside the i == 1 loop branch before transfer.
    """

    async def producer_episode(i):
        part = f"part_{i}"
        source = f"source_{i}"
        buf = f"buffer_{i}"
        ready = f"ready_{i}"
        empty = "empty_0"

        # LONG: acquire tool before source pickup and keep it across the
        # second-item wait and checks.
        await robot.acquire("LEFT", "tool", 120)

        if i == 1:
            # Producer waits and clears empty_0 before entering buffer with
            # the second part.
            empty_rcpt = await robot.wait_event(empty, 120)
            robot.clear_event(empty, expected_version=empty_rcpt.version)

            # D4: join the two second-item checks with asyncio.gather inside
            # the i == 1 loop branch before transfer.
            async def check_line_clear():
                return await robot.inspect("LEFT", "line_clear")

            async def check_receiver_ready():
                return await robot.inspect("RIGHT", "receiver_ready")

            lc_obs, rr_obs = await asyncio.gather(
                check_line_clear(), check_receiver_ready()
            )
            if not (lc_obs.value.get("clear") is True
                    and lc_obs.value.get("item_id") == "part_1"
                    and rr_obs.value.get("ready") is True
                    and rr_obs.value.get("item_id") == "part_1"):
                await robot.release_resource("LEFT", "tool")
                return

        # Approach source and immediately grasp (same virtual moment).
        await robot.move("LEFT", "left_wait")
        await robot.move("LEFT", source)
        await robot.grasp("LEFT", part)

        # Both participants own buffer_lock during buffer entry and departure.
        await robot.acquire("LEFT", "buffer_lock", 120)

        # Move to buffer and place; immediately depart before ready
        # publication.
        await robot.move("LEFT", buf)
        await robot.release("LEFT", part, buf)
        await robot.move("LEFT", "left_wait")

        # Release lock on departure.
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready receipt for consumer.
        ready_rcpt = robot.signal(ready, part)

        # Producer departs home before yielding.
        await robot.move("LEFT", "left_home")

        # Release tool on every normal exit.
        await robot.release_resource("LEFT", "tool")

        return ready_rcpt

    async def consumer_episode(i, ready_rcpt):
        part = f"part_{i}"
        buf = f"buffer_{i}"
        target = f"target_{i}"
        empty = "empty_0"

        # Consumer waits the corresponding ready receipt before pickup.
        waited_rcpt = await robot.wait_event(ready_rcpt.event_id, 120)

        # Both participants own buffer_lock during buffer entry and departure.
        await robot.acquire("RIGHT", "buffer_lock", 120)

        # Approach buffer and immediately grasp (same virtual moment).
        await robot.move("RIGHT", "right_wait")
        await robot.move("RIGHT", buf)
        await robot.grasp("RIGHT", part)

        # Depart buffer with the carried object; supply the exact active item
        # receipt on the carried move to target.
        await robot.move("RIGHT", "right_wait")
        await robot.move("RIGHT", target, receipt=waited_rcpt)

        # Consumer clears ready after its carried move.
        robot.clear_event(ready_rcpt.event_id,
                          expected_version=waited_rcpt.version)

        # Release on target and depart before publishing empty_0.
        await robot.release("RIGHT", part, target)
        await robot.move("RIGHT", "right_wait")

        # Release lock on departure.
        await robot.release_resource("RIGHT", "buffer_lock")

        # Depart home before publishing empty.
        await robot.move("RIGHT", "right_home")

        # Publish empty_0 receipt for producer.
        empty_rcpt = robot.signal(empty, part)

        return empty_rcpt

    async def runner_b():
        # B runs producer and consumer coroutines together.
        for i in range(2):
            ready_rcpt = await producer_episode(i)
            if ready_rcpt is None:
                return
            await consumer_episode(i, ready_rcpt)

    await runner_b()
