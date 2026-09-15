import asyncio
from bridge_robot_api import MotionFault


async def run_task(robot):
    """D4_ATTR_NESTED-SHORT-L0: capacity-one buffer handoff.

    A alternates producer/consumer episodes; B runs producer and consumer
    coroutines together. D4 joins the two second-item checks with
    asyncio.gather inside the i == 1 loop branch before transfer.
    """

    # ---- helpers ----------------------------------------------------------

    async def acquire_lock(arm, resource_id, timeout_s=4):
        return await robot.acquire(arm, resource_id, timeout_s)

    async def release_lock(arm, resource_id):
        return await robot.release_resource(arm, resource_id)

    async def release_tool(arm):
        try:
            await robot.release_resource(arm, "tool")
        except Exception:
            pass

    async def safe_release_lock(arm, resource_id):
        try:
            await robot.release_resource(arm, resource_id)
        except Exception:
            pass

    # ---- producer: LEFT picks part_i from source, places at buffer_i ----

    async def producer_episode(i):
        part = f"part_{i}"
        source = f"source_{i}"
        buffer = f"buffer_{i}"
        ready_event = f"ready_{i}"

        # LEFT owns tool during every buffer placement.
        await acquire_lock("LEFT", "tool", 4)
        try:
            await acquire_lock("LEFT", "buffer_lock", 4)
            try:
                # Approach source_i from left_home, then immediately grasp.
                await robot.move("LEFT", "left_home")
                await robot.move("LEFT", source)
                await robot.grasp("LEFT", part)

                # Carry to buffer_i and release, then immediately depart.
                await robot.move("LEFT", buffer)
                await robot.release("LEFT", part, buffer)
                await robot.move("LEFT", "left_home")
            finally:
                await safe_release_lock("LEFT", "buffer_lock")
        finally:
            await release_tool("LEFT")

        # Publish ready_i after departing from buffer.
        robot.signal(ready_event, part)

    # ---- consumer: RIGHT picks part_i from buffer, carries to target_i --

    async def consumer_episode(i):
        part = f"part_{i}"
        buffer = f"buffer_{i}"
        target = f"target_{i}"
        ready_event = f"ready_{i}"

        # Wait for the corresponding ready receipt before pickup.
        ready_receipt = await robot.wait_event(ready_event, 30)

        # SHORT acquires tool only after any second-item wait and checks.
        if i == 1:
            # D4 joins the two second-item checks with asyncio.gather.
            line_obs, recv_obs = await asyncio.gather(
                robot.inspect("LEFT", "line_clear"),
                robot.inspect("RIGHT", "receiver_ready"),
            )
            if not (line_obs.value.get("clear") is True
                    and recv_obs.value.get("ready") is True):
                raise RuntimeError("second-item transfer checks failed")

            await acquire_lock("RIGHT", "tool", 4)
        else:
            await acquire_lock("RIGHT", "tool", 4)

        try:
            await acquire_lock("RIGHT", "buffer_lock", 4)
            try:
                # Approach buffer_i from right_home, then immediately grasp.
                await robot.move("RIGHT", "right_home")
                await robot.move("RIGHT", buffer)
                await robot.grasp("RIGHT", part)

                # Carried move to target uses the exact active item receipt.
                await robot.move("RIGHT", target, receipt=ready_receipt)

                # Clear ready after the carried move completes.
                robot.clear_event(ready_event, expected_version=ready_receipt.version)

                # Release on target and depart before publishing empty_0.
                await robot.release("RIGHT", part, target)
                await robot.move("RIGHT", "right_home")
            finally:
                await safe_release_lock("RIGHT", "buffer_lock")
        finally:
            await release_tool("RIGHT")

        # Publish empty_0 after departing from buffer.
        robot.signal("empty_0", part)

    # ---- episode orchestration -------------------------------------------

    async def episode(i):
        if i == 0:
            # A alternates complete producer/consumer episodes.
            await producer_episode(0)
            await consumer_episode(0)
        else:
            # B runs producer and consumer coroutines together.
            prod = asyncio.create_task(producer_episode(1))
            cons = asyncio.create_task(consumer_episode(1))
            await prod
            await cons

    # Episode 0: part_0 source_0 -> buffer_0 -> target_0.
    await episode(0)

    # Producer waits and clears empty_0 before entering buffer with second part.
    empty_receipt = await robot.wait_event("empty_0", 30)
    robot.clear_event("empty_0", expected_version=empty_receipt.version)

    # Episode 1: part_1 source_1 -> buffer_1 -> target_1.
    await episode(1)
