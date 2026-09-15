import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Shared state for coordination between producer and consumer coroutines.
    ready_receipts: dict[str, object] = {}
    empty_receipt: dict[str, object] = {}
    stop = False

    async def producer_part_0() -> None:
        nonlocal stop
        # LEFT owns tool from before source pickup through ready publication.
        await robot.acquire("LEFT", "tool", 120)
        await robot.set_mode("LEFT", "tool", "OFF")

        # Approach source_0 from left_home, then immediately grasp part_0.
        await robot.move("LEFT", "source_0", 4)
        await robot.grasp("LEFT", "part_0")

        # Acquire buffer_lock for buffer entry.
        await robot.acquire("LEFT", "buffer_lock", 120)
        await robot.set_mode("LEFT", "buffer_lock", "OFF")

        # Transport part_0 to buffer_0.
        await robot.move("LEFT", "buffer_0", 4)

        # Release part_0 at buffer_0, then immediately depart.
        await robot.release("LEFT", "part_0", "buffer_0")
        await robot.move("LEFT", "left_home", 4)

        # Release buffer_lock on exit.
        await robot.set_mode("LEFT", "buffer_lock", "OFF")
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready_0 after departure.
        r = robot.signal("ready_0", "part_0")
        ready_receipts["part_0"] = r

        # Release tool on exit.
        await robot.set_mode("LEFT", "tool", "OFF")
        await robot.release_resource("LEFT", "tool")

    async def consumer_part_0() -> None:
        nonlocal stop
        # Wait for ready_0 receipt before pickup.
        r = await robot.wait_event("ready_0", 120)
        ready_receipts["part_0"] = r

        # RIGHT owns tool for pickup and carried move.
        await robot.acquire("RIGHT", "tool", 120)
        await robot.set_mode("RIGHT", "tool", "OFF")

        # Acquire buffer_lock for buffer entry.
        await robot.acquire("RIGHT", "buffer_lock", 120)
        await robot.set_mode("RIGHT", "buffer_lock", "OFF")

        # Approach buffer_0 from right_home, then immediately grasp part_0.
        await robot.move("RIGHT", "buffer_0", 4)
        await robot.grasp("RIGHT", "part_0")

        # Carried move to target_0, supplying the exact active item receipt.
        await robot.move("RIGHT", "target_0", 4, receipt=ready_receipts["part_0"])

        # Clear ready_0 after carried move.
        robot.clear_event("ready_0", expected_version=ready_receipts["part_0"].version)

        # Release part_0 at target_0, then immediately depart.
        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_home", 4)

        # Release buffer_lock on exit.
        await robot.set_mode("RIGHT", "buffer_lock", "OFF")
        await robot.release_resource("RIGHT", "buffer_lock")

        # Release tool on exit.
        await robot.set_mode("RIGHT", "tool", "OFF")
        await robot.release_resource("RIGHT", "tool")

        # Publish empty_0 after departure.
        e = robot.signal("empty_0", "part_0")
        empty_receipt["part_0"] = e

    async def producer_part_1() -> None:
        nonlocal stop
        # Wait for empty_0 before entering buffer with second part.
        e = await robot.wait_event("empty_0", 120)
        empty_receipt["part_0"] = e

        # Clear empty_0 before entering buffer with second part.
        robot.clear_event("empty_0", expected_version=empty_receipt["part_0"].version)

        # LEFT owns tool from before source pickup through ready publication.
        await robot.acquire("LEFT", "tool", 120)
        await robot.set_mode("LEFT", "tool", "OFF")

        # Move to left_wait, then approach source_1, then immediately grasp part_1.
        await robot.move("LEFT", "left_wait", 4)
        await robot.move("LEFT", "source_1", 4)
        await robot.grasp("LEFT", "part_1")

        # Acquire buffer_lock for buffer entry.
        await robot.acquire("LEFT", "buffer_lock", 120)
        await robot.set_mode("LEFT", "buffer_lock", "OFF")

        # Transport part_1 to buffer_1.
        await robot.move("LEFT", "buffer_1", 4)

        # Release part_1 at buffer_1, then immediately depart.
        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.move("LEFT", "left_home", 4)

        # Release buffer_lock on exit.
        await robot.set_mode("LEFT", "buffer_lock", "OFF")
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready_1 after departure.
        r = robot.signal("ready_1", "part_1")
        ready_receipts["part_1"] = r

        # Release tool on exit.
        await robot.set_mode("LEFT", "tool", "OFF")
        await robot.release_resource("LEFT", "tool")

    async def consumer_part_1() -> None:
        nonlocal stop
        # Wait for ready_1 receipt before pickup.
        r = await robot.wait_event("ready_1", 120)
        ready_receipts["part_1"] = r

        # RIGHT owns tool for pickup and carried move.
        await robot.acquire("RIGHT", "tool", 120)
        await robot.set_mode("RIGHT", "tool", "OFF")

        # Acquire buffer_lock for buffer entry.
        await robot.acquire("RIGHT", "buffer_lock", 120)
        await robot.set_mode("RIGHT", "buffer_lock", "OFF")

        # Move to right_wait, then approach buffer_1, then immediately grasp part_1.
        await robot.move("RIGHT", "right_wait", 4)
        await robot.move("RIGHT", "buffer_1", 4)
        await robot.grasp("RIGHT", "part_1")

        # Carried move to target_1, supplying the exact active item receipt.
        await robot.move("RIGHT", "target_1", 4, receipt=ready_receipts["part_1"])

        # Clear ready_1 after carried move.
        robot.clear_event("ready_1", expected_version=ready_receipts["part_1"].version)

        # Release part_1 at target_1, then immediately depart.
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home", 4)

        # Release buffer_lock on exit.
        await robot.set_mode("RIGHT", "buffer_lock", "OFF")
        await robot.release_resource("RIGHT", "buffer_lock")

        # Release tool on exit.
        await robot.set_mode("RIGHT", "tool", "OFF")
        await robot.release_resource("RIGHT", "tool")

    # Episode A: serial alternating producer/consumer episodes for part_0.
    await producer_part_0()
    await consumer_part_0()

    # Episode B: joined producer and consumer coroutines for part_1.
    # For item 1, wait and clear empty_0, then inspect both readiness facts;
    # C8 joins the two checks inside the loop branch.
    async def joined_part_1() -> None:
        # Wait and clear empty_0 before entering buffer with second part.
        e = await robot.wait_event("empty_0", 120)
        empty_receipt["part_0"] = e
        robot.clear_event("empty_0", expected_version=empty_receipt["part_0"].version)

        # Inspect both readiness facts; C8 joins the two checks inside the loop branch.
        line_clear_obs = await robot.inspect("LEFT", "line_clear")
        receiver_ready_obs = await robot.inspect("LEFT", "receiver_ready")

        # Run producer and consumer coroutines together.
        await asyncio.gather(producer_part_1_inner(), consumer_part_1_inner())

    async def producer_part_1_inner() -> None:
        # LEFT owns tool from before source pickup through ready publication.
        await robot.acquire("LEFT", "tool", 120)
        await robot.set_mode("LEFT", "tool", "OFF")

        # Move to left_wait, then approach source_1, then immediately grasp part_1.
        await robot.move("LEFT", "left_wait", 4)
        await robot.move("LEFT", "source_1", 4)
        await robot.grasp("LEFT", "part_1")

        # Acquire buffer_lock for buffer entry.
        await robot.acquire("LEFT", "buffer_lock", 120)
        await robot.set_mode("LEFT", "buffer_lock", "OFF")

        # Transport part_1 to buffer_1.
        await robot.move("LEFT", "buffer_1", 4)

        # Release part_1 at buffer_1, then immediately depart.
        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.move("LEFT", "left_home", 4)

        # Release buffer_lock on exit.
        await robot.set_mode("LEFT", "buffer_lock", "OFF")
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready_1 after departure.
        r = robot.signal("ready_1", "part_1")
        ready_receipts["part_1"] = r

        # Release tool on exit.
        await robot.set_mode("LEFT", "tool", "OFF")
        await robot.release_resource("LEFT", "tool")

    async def consumer_part_1_inner() -> None:
        # Wait for ready_1 receipt before pickup.
        r = await robot.wait_event("ready_1", 120)
        ready_receipts["part_1"] = r

        # RIGHT owns tool for pickup and carried move.
        await robot.acquire("RIGHT", "tool", 120)
        await robot.set_mode("RIGHT", "tool", "OFF")

        # Acquire buffer_lock for buffer entry.
        await robot.acquire("RIGHT", "buffer_lock", 120)
        await robot.set_mode("RIGHT", "buffer_lock", "OFF")

        # Move to right_wait, then approach buffer_1, then immediately grasp part_1.
        await robot.move("RIGHT", "right_wait", 4)
        await robot.move("RIGHT", "buffer_1", 4)
        await robot.grasp("RIGHT", "part_1")

        # Carried move to target_1, supplying the exact active item receipt.
        await robot.move("RIGHT", "target_1", 4, receipt=ready_receipts["part_1"])

        # Clear ready_1 after carried move.
        robot.clear_event("ready_1", expected_version=ready_receipts["part_1"].version)

        # Release part_1 at target_1, then immediately depart.
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home", 4)

        # Release buffer_lock on exit.
        await robot.set_mode("RIGHT", "buffer_lock", "OFF")
        await robot.release_resource("RIGHT", "buffer_lock")

        # Release tool on exit.
        await robot.set_mode("RIGHT", "tool", "OFF")
        await robot.release_resource("RIGHT", "tool")

    await joined_part_1()
