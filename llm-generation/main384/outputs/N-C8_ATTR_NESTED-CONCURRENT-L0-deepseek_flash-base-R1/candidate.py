import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # C8_ATTR_NESTED-CONCURRENT-L0
    # Two distinct parts cross a capacity-one supported buffer from LEFT
    # producer to RIGHT consumer.  Variant CONCURRENT: producer and
    # consumer coroutines run together (joined), with the buffer_lock
    # serializing buffer entry/departure.
    # ------------------------------------------------------------------

    # ---- shared state -------------------------------------------------
    # The buffer is capacity-one.  buffer_0 and buffer_1 name the same
    # physical capacity-one buffer at identical coordinates, with
    # item-specific pickup contracts.  We track which item currently
    # occupies the buffer (None = empty).
    buffer_occupied = {"item": None}

    # ------------------------------------------------------------------
    # Producer coroutine (LEFT arm)
    # ------------------------------------------------------------------
    async def producer() -> None:
        # Episode 1: part_0
        # LEFT owns tool from before each source pickup through ready
        # publication and releases it on every exit.
        await robot.acquire("LEFT", "tool", 5.0)
        try:
            # Approach source_0 from left_home, then immediately grasp.
            await robot.move("LEFT", "source_0")
            await robot.grasp("LEFT", "part_0")

            # Carry part_0 to buffer_0.  Both participants own buffer_lock
            # during buffer entry and departure.
            await robot.acquire("LEFT", "buffer_lock", 5.0)
            try:
                await robot.move("LEFT", "buffer_0")
                await robot.release("LEFT", "part_0", "buffer_0")
                buffer_occupied["item"] = "part_0"
                # Producer places each part at buffer and immediately
                # departs before ready publication.
                await robot.move("LEFT", "left_wait")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")

            # Publish ready_0 for part_0.
            robot.signal("ready_0", "part_0")

            # Wait for empty_0 before entering buffer with the second part.
            # (empty_0 is signaled by the consumer after it clears ready_0
            # and departs from target.)
            receipt_empty = await robot.wait_event("empty_0", 30.0)
            robot.clear_event("empty_0", expected_version=receipt_empty.version)

            # Episode 2: part_1
            # For item 1, wait and clear empty_0, then inspect both
            # readiness facts; C8 joins the two checks inside the loop
            # branch.
            # (empty_0 already waited/cleared above.)
            # Joined inspection of both readiness facts.
            obs_line, obs_recv = await asyncio.gather(
                robot.inspect("LEFT", "line_clear"),
                robot.inspect("LEFT", "receiver_ready"),
            )
            # Both facts must indicate readiness for part_1.
            line_val = obs_line.value
            recv_val = obs_recv.value
            if not (isinstance(line_val, dict) and line_val.get("clear") is True
                    and line_val.get("item_id") == "part_1"):
                raise ContractError("line_clear not ready for part_1")
            if not (isinstance(recv_val, dict) and recv_val.get("ready") is True
                    and recv_val.get("item_id") == "part_1"):
                raise ContractError("receiver_ready not ready for part_1")

            # Approach source_1 from left_wait, then immediately grasp.
            await robot.move("LEFT", "source_1")
            await robot.grasp("LEFT", "part_1")

            # Carry part_1 to buffer_1 (same physical buffer).
            await robot.acquire("LEFT", "buffer_lock", 5.0)
            try:
                await robot.move("LEFT", "buffer_1")
                await robot.release("LEFT", "part_1", "buffer_1")
                buffer_occupied["item"] = "part_1"
                # Immediately depart before ready publication.
                await robot.move("LEFT", "left_wait")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")

            # Publish ready_1 for part_1.
            robot.signal("ready_1", "part_1")
        finally:
            # LEFT releases tool on every exit.
            await robot.release_resource("LEFT", "tool")

    # ------------------------------------------------------------------
    # Consumer coroutine (RIGHT arm)
    # ------------------------------------------------------------------
    async def consumer() -> None:
        # Episode 1: part_0
        # Consumer waits the corresponding ready receipt before pickup.
        receipt_ready0 = await robot.wait_event("ready_0", 30.0)

        # Enter buffer under buffer_lock.
        await robot.acquire("RIGHT", "buffer_lock", 5.0)
        try:
            # Approach buffer_0 from right_home, then immediately grasp.
            await robot.move("RIGHT", "buffer_0")
            await robot.grasp("RIGHT", "part_0")
            buffer_occupied["item"] = None
            # Depart buffer.
            await robot.move("RIGHT", "right_wait")
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")

        # Supply the exact active item receipt on carried move to target.
        await robot.move("RIGHT", "target_0", receipt=receipt_ready0)

        # Consumer clears ready after its carried move.
        robot.clear_event("ready_0", expected_version=receipt_ready0.version)

        # Release on target and depart before publishing empty_0.
        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_home")

        # Publish empty_0.
        robot.signal("empty_0")

        # Episode 2: part_1
        receipt_ready1 = await robot.wait_event("ready_1", 30.0)

        await robot.acquire("RIGHT", "buffer_lock", 5.0)
        try:
            # Approach buffer_1 from right_wait, then immediately grasp.
            await robot.move("RIGHT", "buffer_1")
            await robot.grasp("RIGHT", "part_1")
            buffer_occupied["item"] = None
            await robot.move("RIGHT", "right_wait")
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")

        await robot.move("RIGHT", "target_1", receipt=receipt_ready1)

        robot.clear_event("ready_1", expected_version=receipt_ready1.version)

        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home")

        robot.signal("empty_0")

    # ------------------------------------------------------------------
    # Variant CONCURRENT: run producer and consumer coroutines together.
    # ------------------------------------------------------------------
    await asyncio.gather(producer(), consumer())
