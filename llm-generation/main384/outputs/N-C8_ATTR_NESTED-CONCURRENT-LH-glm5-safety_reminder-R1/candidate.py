import asyncio
from bridge_robot_api import MotionFault


async def run_task(robot):
    # C8_ATTR_NESTED-CONCURRENT-LH:
    # A = LEFT: serial alternating producer episodes (part_0 then part_1).
    # B = RIGHT: producer+consumer coroutines joined together.
    # Capacity-one buffer (buffer_0 == buffer_1 same coordinates).
    # Mechanism BUFFER_RECEIPT: ready receipt supplied on carried move to target.
    # LEFT owns tool from before each source pickup through ready publication,
    # releases tool on every exit. h_variant.invalidates=true: refresh readiness
    # facts inside the loop branch for item 1.

    async def acquire_tool():
        await robot.acquire("LEFT", "tool", 120)
        await robot.set_mode("LEFT", "tool", "OFF")

    async def release_tool():
        await robot.set_mode("LEFT", "tool", "OFF")
        await robot.release_resource("LEFT", "tool")

    async def acquire_buffer_lock(arm):
        await robot.acquire(arm, "buffer_lock", 120)
        await robot.set_mode(arm, "buffer_lock", "OFF")

    async def release_buffer_lock(arm):
        await robot.set_mode(arm, "buffer_lock", "OFF")
        await robot.release_resource(arm, "buffer_lock")

    async def left_produce_part_0():
        # Episode A1: LEFT produces part_0 to buffer_0, departs, then publishes ready_0.
        await acquire_tool()
        await robot.move("LEFT", "source_0")
        await robot.grasp("LEFT", "part_0")
        await robot.move("LEFT", "left_wait")
        await acquire_buffer_lock("LEFT")
        await robot.move("LEFT", "buffer_0")
        await robot.release("LEFT", "part_0", "buffer_0")
        await robot.move("LEFT", "left_wait")
        await release_buffer_lock("LEFT")
        await release_tool()
        # Producer places each part at buffer and immediately departs before ready publication.
        robot.signal("ready_0", "part_0")

    async def left_produce_part_1():
        # Episode A2: LEFT produces part_1 to buffer_1, departs, then publishes ready_1.
        # For item 1: wait and clear empty_0, then inspect both readiness facts;
        # C8 joins the two checks inside the loop branch.
        empty_receipt = await robot.wait_event("empty_0", 120)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

        # Join both readiness fact checks inside the loop branch.
        receiver_ready_obs = await robot.inspect("RIGHT", "receiver_ready")
        line_clear_obs = await robot.inspect("RIGHT", "line_clear")
        rr = receiver_ready_obs.value
        lc = line_clear_obs.value
        if not (rr.get("item_id") == "part_1" and rr.get("ready") is True):
            raise RuntimeError("receiver_ready not valid for part_1")
        if not (lc.get("item_id") == "part_1" and lc.get("clear") is True):
            raise RuntimeError("line_clear not valid for part_1")

        await acquire_tool()
        await robot.move("LEFT", "source_1")
        await robot.grasp("LEFT", "part_1")
        await robot.move("LEFT", "left_wait")
        await acquire_buffer_lock("LEFT")
        await robot.move("LEFT", "buffer_1")
        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.move("LEFT", "left_wait")
        await release_buffer_lock("LEFT")
        await release_tool()
        # Producer places each part at buffer and immediately departs before ready publication.
        robot.signal("ready_1", "part_1")

    async def right_consume_part_0():
        # B consumer coroutine for part_0: wait ready_0, pickup, carry to target
        # supplying exact active item receipt, clear ready after carried move,
        # release on target, depart, then publish empty_0.
        ready_receipt = await robot.wait_event("ready_0", 120)
        await acquire_buffer_lock("RIGHT")
        await robot.move("RIGHT", "buffer_0")
        await robot.grasp("RIGHT", "part_0")
        await robot.move("RIGHT", "right_wait")
        await release_buffer_lock("RIGHT")
        # Supply exact active item receipt on carried move to target.
        await robot.move("RIGHT", "target_0", receipt=ready_receipt)
        # Consumer clears ready after its carried move.
        robot.clear_event("ready_0", expected_version=ready_receipt.version)
        await robot.release("RIGHT", "part_0", "target_0")
        # Depart before publishing empty_0.
        await robot.move("RIGHT", "right_home")
        robot.signal("empty_0", "part_0")

    async def right_consume_part_1():
        # B consumer coroutine for part_1: wait ready_1, pickup, carry to target
        # supplying exact active item receipt, clear ready after carried move,
        # release on target, depart. (No empty publication needed after final part.)
        ready_receipt = await robot.wait_event("ready_1", 120)
        await acquire_buffer_lock("RIGHT")
        await robot.move("RIGHT", "buffer_1")
        await robot.grasp("RIGHT", "part_1")
        await robot.move("RIGHT", "right_wait")
        await release_buffer_lock("RIGHT")
        # Supply exact active item receipt on carried move to target.
        await robot.move("RIGHT", "target_1", receipt=ready_receipt)
        # Consumer clears ready after its carried move.
        robot.clear_event("ready_1", expected_version=ready_receipt.version)
        await robot.release("RIGHT", "part_1", "target_1")
        # Depart to home.
        await robot.move("RIGHT", "right_home")

    async def left_runner():
        # A alternates complete producer/consumer episodes.
        await left_produce_part_0()
        await left_produce_part_1()
        # LEFT returns home after final episode.
        await robot.move("LEFT", "left_home")

    async def right_runner():
        # B runs producer and consumer coroutines together.
        # RIGHT has no producer role in LH; it runs consumer episodes concurrently
        # with LEFT's production, synchronized by ready/empty events.
        await right_consume_part_0()
        await right_consume_part_1()

    await asyncio.gather(left_runner(), right_runner())
