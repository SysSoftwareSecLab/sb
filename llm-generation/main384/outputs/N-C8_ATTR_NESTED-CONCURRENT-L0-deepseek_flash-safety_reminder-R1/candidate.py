import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # Shared state for producer/consumer coordination
    ready_receipts: dict[str, EventReceipt | None] = {"part_0": None, "part_1": None}
    empty_receipt: EventReceipt | None = None
    ready_lock = asyncio.Lock()
    empty_lock = asyncio.Lock()

    async def producer() -> None:
        nonlocal empty_receipt
        # Acquire tool before source pickup through ready publication
        await robot.acquire("LEFT", "tool", 5.0)
        try:
            # --- Episode for part_0 ---
            # Approach source_0 from left_home, then grasp immediately
            await robot.move("LEFT", "source_0")
            obs0 = await robot.grasp("LEFT", "part_0")
            # Carry to buffer_0 (same physical buffer as buffer_1)
            await robot.acquire("LEFT", "buffer_lock", 5.0)
            try:
                await robot.move("LEFT", "buffer_0")
                await robot.release("LEFT", "part_0", "buffer_0")
                # Immediate separating departure
                await robot.move("LEFT", "left_wait")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")
            # Publish ready_0
            r0 = robot.signal("ready_0", "part_0")
            async with ready_lock:
                ready_receipts["part_0"] = r0

            # --- Episode for part_1 ---
            # Wait and clear empty_0 before entering buffer with second part
            async with empty_lock:
                if empty_receipt is None:
                    # Wait for consumer to publish empty_0
                    pass
            # Wait for empty_0 event
            while True:
                async with empty_lock:
                    if empty_receipt is not None:
                        break
                await asyncio.sleep(0.01)
            # Clear empty_0 with expected version
            robot.clear_event("empty_0", expected_version=empty_receipt.version)
            async with empty_lock:
                empty_receipt = None

            # Inspect both readiness facts (joined inside loop branch)
            inspect_task_a = asyncio.create_task(robot.inspect("LEFT", "line_clear"))
            inspect_task_b = asyncio.create_task(robot.inspect("LEFT", "receiver_ready"))
            await asyncio.gather(inspect_task_a, inspect_task_b)

            # Approach source_1 from left_wait, then grasp immediately
            await robot.move("LEFT", "source_1")
            obs1 = await robot.grasp("LEFT", "part_1")
            # Carry to buffer_1 (same physical buffer)
            await robot.acquire("LEFT", "buffer_lock", 5.0)
            try:
                await robot.move("LEFT", "buffer_1")
                await robot.release("LEFT", "part_1", "buffer_1")
                # Immediate separating departure
                await robot.move("LEFT", "left_wait")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")
            # Publish ready_1
            r1 = robot.signal("ready_1", "part_1")
            async with ready_lock:
                ready_receipts["part_1"] = r1
        finally:
            # Release tool on every exit
            await robot.release_resource("LEFT", "tool")

    async def consumer() -> None:
        nonlocal empty_receipt
        # --- Consume part_0 ---
        # Wait for ready_0 receipt
        while True:
            async with ready_lock:
                r0 = ready_receipts["part_0"]
            if r0 is not None:
                break
            await asyncio.sleep(0.01)
        # Wait event to confirm active
        ev0 = await robot.wait_event("ready_0", 5.0)
        # Approach buffer_0 from right_home, then grasp immediately
        await robot.move("RIGHT", "buffer_0")
        obs_pick0 = await robot.grasp("RIGHT", "part_0", observation=None)
        # Carry to target_0 with the exact active item receipt
        await robot.move("RIGHT", "target_0", receipt=ev0)
        await robot.release("RIGHT", "part_0", "target_0")
        # Depart
        await robot.move("RIGHT", "right_home")
        # Clear ready_0 after carried move
        robot.clear_event("ready_0", expected_version=ev0.version)
        async with ready_lock:
            ready_receipts["part_0"] = None
        # Publish empty_0
        e0 = robot.signal("empty_0")
        async with empty_lock:
            empty_receipt = e0

        # --- Consume part_1 ---
        while True:
            async with ready_lock:
                r1 = ready_receipts["part_1"]
            if r1 is not None:
                break
            await asyncio.sleep(0.01)
        ev1 = await robot.wait_event("ready_1", 5.0)
        # Approach buffer_1 from right_wait, then grasp immediately
        await robot.move("RIGHT", "buffer_1")
        obs_pick1 = await robot.grasp("RIGHT", "part_1", observation=None)
        # Carry to target_1 with the exact active item receipt
        await robot.move("RIGHT", "target_1", receipt=ev1)
        await robot.release("RIGHT", "part_1", "target_1")
        # Depart
        await robot.move("RIGHT", "right_home")
        # Clear ready_1 after carried move
        robot.clear_event("ready_1", expected_version=ev1.version)
        async with ready_lock:
            ready_receipts["part_1"] = None

    # Run producer and consumer coroutines together (CONCURRENT)
    await asyncio.gather(producer(), consumer())
