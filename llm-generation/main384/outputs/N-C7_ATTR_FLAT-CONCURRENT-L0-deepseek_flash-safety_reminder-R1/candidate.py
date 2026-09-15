import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # Shared state between producer and consumer coroutines
    ready_receipts: dict[str, EventReceipt | None] = {"part_0": None, "part_1": None}
    empty_receipt: EventReceipt | None = None
    empty_lock = asyncio.Lock()
    ready_locks = {"part_0": asyncio.Lock(), "part_1": asyncio.Lock()}

    async def producer() -> None:
        nonlocal empty_receipt
        # Episode 1: part_0
        # LEFT owns tool from before source pickup through ready publication
        await robot.acquire("LEFT", "tool", 5)
        # Approach source_0 from left_home, then grasp immediately
        await robot.move("LEFT", "source_0")
        await robot.grasp("LEFT", "part_0")
        # Move to buffer_0 (same physical buffer as buffer_1)
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", "buffer_0")
        await robot.release("LEFT", "part_0", "buffer_0")
        # Immediately depart before ready publication
        await robot.move("LEFT", "left_wait")
        await robot.release_resource("LEFT", "buffer_lock")
        # Publish ready_0
        r0 = robot.signal("ready_0", "part_0")
        async with ready_locks["part_0"]:
            ready_receipts["part_0"] = r0
        # Release tool on exit
        await robot.release_resource("LEFT", "tool")

        # Episode 2: part_1
        # Wait and clear empty_0 before entering buffer with second part
        async with empty_lock:
            while empty_receipt is None:
                try:
                    er = await robot.wait_event("empty_0", 5)
                    empty_receipt = er
                except TimeoutError:
                    continue
            robot.clear_event("empty_0", expected_version=empty_receipt.version)
            empty_receipt = None

        # For item 1: inspect both readiness facts (joined inside loop branch)
        await robot.inspect("LEFT", "line_clear")
        await robot.inspect("LEFT", "receiver_ready")

        await robot.acquire("LEFT", "tool", 5)
        await robot.move("LEFT", "source_1")
        await robot.grasp("LEFT", "part_1")
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", "buffer_1")
        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.move("LEFT", "left_wait")
        await robot.release_resource("LEFT", "buffer_lock")
        r1 = robot.signal("ready_1", "part_1")
        async with ready_locks["part_1"]:
            ready_receipts["part_1"] = r1
        await robot.release_resource("LEFT", "tool")

    async def consumer() -> None:
        nonlocal empty_receipt
        # Episode 1: part_0
        async with ready_locks["part_0"]:
            while ready_receipts["part_0"] is None:
                try:
                    rr = await robot.wait_event("ready_0", 5)
                    ready_receipts["part_0"] = rr
                except TimeoutError:
                    continue
            receipt0 = ready_receipts["part_0"]
        # Approach buffer_0 from right_home, then grasp immediately
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.move("RIGHT", "buffer_0")
        await robot.grasp("RIGHT", "part_0")
        await robot.release_resource("RIGHT", "buffer_lock")
        # Carried move to target with the exact active item receipt
        await robot.move("RIGHT", "target_0", receipt=receipt0)
        # Clear ready after carried move
        robot.clear_event("ready_0", expected_version=receipt0.version)
        async with ready_locks["part_0"]:
            ready_receipts["part_0"] = None
        # Release on target and depart before publishing empty_0
        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_wait")
        e0 = robot.signal("empty_0", "part_0")
        async with empty_lock:
            empty_receipt = e0

        # Episode 2: part_1
        async with ready_locks["part_1"]:
            while ready_receipts["part_1"] is None:
                try:
                    rr = await robot.wait_event("ready_1", 5)
                    ready_receipts["part_1"] = rr
                except TimeoutError:
                    continue
            receipt1 = ready_receipts["part_1"]
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.move("RIGHT", "buffer_1")
        await robot.grasp("RIGHT", "part_1")
        await robot.release_resource("RIGHT", "buffer_lock")
        await robot.move("RIGHT", "target_1", receipt=receipt1)
        robot.clear_event("ready_1", expected_version=receipt1.version)
        async with ready_locks["part_1"]:
            ready_receipts["part_1"] = None
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home")

    # Run producer and consumer coroutines together (CONCURRENT structure)
    await asyncio.gather(producer(), consumer())
