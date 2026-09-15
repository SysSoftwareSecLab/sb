import asyncio
from bridge_robot_api import MotionFault


async def run_task(robot):
    # D3_ATTR_FLAT-SHORT-L0
    # SHORT: acquire tool only after second-item wait and checks; release tool on every exit.

    async def producer_episode(i):
        # Produce part_i: LEFT picks from source_i, carries to buffer_i, releases, departs.
        part = f"part_{i}"
        source = f"source_{i}"
        buffer = f"buffer_{i}"

        # Approach source_i from left_home (i==0) or left_wait (i==1) and grasp immediately.
        start = "left_home" if i == 0 else "left_wait"
        await robot.move("LEFT", start)
        await robot.grasp("LEFT", part)

        # Carry to buffer.
        await robot.move("LEFT", buffer)

        # Own buffer_lock during placement and departure.
        await robot.acquire("LEFT", "buffer_lock", 5)
        try:
            await robot.release("LEFT", part, buffer)
            # Immediate separating departure from buffer.
            await robot.move("LEFT", start)
        finally:
            await robot.set_mode("LEFT", "buffer_lock", "OFF")
            await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready_i after departing buffer.
        ready_event = f"ready_{i}"
        ready_receipt = robot.signal(ready_event, part)

        # For second item, after empty_0 is waited and cleared, perform checks with tool held.
        if i == 1:
            # SHORT: acquire tool after second-item wait and checks.
            await robot.wait_event("empty_0", 5)
            # D3: perform the two checks serially.
            line_obs = await robot.inspect("LEFT", "line_clear")
            recv_obs = await robot.inspect("RIGHT", "receiver_ready")
            line_val = line_obs.value
            recv_val = recv_obs.value
            if not (line_val.get("clear") is True and line_val.get("item_id") == part):
                raise RuntimeError("line_clear check failed")
            if not (recv_val.get("ready") is True and recv_val.get("item_id") == part):
                raise RuntimeError("receiver_ready check failed")

            # Acquire tool after checks; release on all exits.
            await robot.acquire("LEFT", "tool", 5)
            try:
                # Clear empty_0 with the exact waited receipt version.
                empty_receipt = await robot.wait_event("empty_0", 5)
                robot.clear_event("empty_0", expected_version=empty_receipt.version)
            finally:
                await robot.set_mode("LEFT", "tool", "OFF")
                await robot.release_resource("LEFT", "tool")
        else:
            # First item: wait for empty_0 to be inactive-safe by waiting ready_0 consumption path.
            # Producer of first item departs and publishes ready_0; consumer clears ready_0 after carried move.
            pass

        return ready_receipt

    async def consumer_episode(i):
        # Consume part_i: RIGHT waits ready_i, picks from buffer_i, carries to target_i, releases, departs.
        part = f"part_{i}"
        buffer = f"buffer_{i}"
        target = f"target_{i}"
        ready_event = f"ready_{i}"

        # Wait for the corresponding ready receipt before pickup.
        ready_receipt = await robot.wait_event(ready_event, 10)

        # Approach buffer_i from right_home (i==0) or right_wait (i==1) and grasp immediately.
        start = "right_home" if i == 0 else "right_wait"
        await robot.move("RIGHT", start)
        await robot.grasp("RIGHT", part)

        # Own buffer_lock during pickup and departure.
        await robot.acquire("RIGHT", "buffer_lock", 5)
        try:
            # Carried move to target using the exact active item receipt.
            await robot.move("RIGHT", target, receipt=ready_receipt)
            # Clear ready after carried move.
            robot.clear_event(ready_event, expected_version=ready_receipt.version)
            # Release on target and depart before publishing empty_0.
            await robot.release("RIGHT", part, target)
            await robot.move("RIGHT", start)
        finally:
            await robot.set_mode("RIGHT", "buffer_lock", "OFF")
            await robot.release_resource("RIGHT", "buffer_lock")

        # Publish empty_0 after departing target.
        empty_receipt = robot.signal("empty_0", part)
        return empty_receipt

    async def participant_a():
        # A alternates complete producer/consumer episodes.
        # Episode 0: produce part_0.
        await producer_episode(0)
        # Episode 1: consume part_0.
        await consumer_episode(0)
        # Episode 2: produce part_1.
        await producer_episode(1)
        # Episode 3: consume part_1.
        await consumer_episode(1)

    async def participant_b():
        # B runs producer and consumer coroutines together for each item.
        for i in range(2):
            p = asyncio.create_task(producer_episode(i))
            c = asyncio.create_task(consumer_episode(i))
            await p
            await c

    await asyncio.gather(participant_a(), participant_b())
