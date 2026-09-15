from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # CONCURRENT variant: producer and consumer coroutines run together.
    # LEFT = producer, RIGHT = consumer.
    # Capacity-one buffer at buffer_0/buffer_1 (same physical location).
    # ------------------------------------------------------------------

    # Shared state between the two coroutines (single-threaded asyncio).
    state = {
        "ready_receipts": {},   # item_id -> EventReceipt (active ready receipt)
        "empty_receipt": None,  # EventReceipt for empty_0
    }

    # ------------------------------------------------------------------
    # Producer (LEFT arm)
    # ------------------------------------------------------------------
    async def producer() -> None:
        # Acquire the tool resource for the whole producer episode.
        await robot.acquire("LEFT", "tool", 5.0)

        try:
            # ---- Episode for part_0 ----
            # Approach source_0 from left_home, then immediately grasp part_0.
            await robot.move("LEFT", "left_home")
            await robot.move("LEFT", "source_0")
            await robot.grasp("LEFT", "part_0")

            # Carry part_0 to buffer_0 (buffer entry requires buffer_lock).
            await robot.acquire("LEFT", "buffer_lock", 5.0)
            try:
                await robot.move("LEFT", "buffer_0")
                await robot.release("LEFT", "part_0", "buffer_0")
                # Immediately depart after release (same coroutine).
                await robot.move("LEFT", "left_wait")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")

            # Publish ready_0 for part_0.
            receipt0 = robot.signal("ready_0", "part_0")
            state["ready_receipts"]["part_0"] = receipt0

            # ---- Episode for part_1 ----
            # Wait for empty_0 before entering buffer with the second part.
            empty_receipt = await robot.wait_event("empty_0", 10.0)
            state["empty_receipt"] = empty_receipt
            robot.clear_event("empty_0", expected_version=empty_receipt.version)

            # Inspect both readiness facts (serial checks).
            await robot.inspect("LEFT", "line_clear")
            await robot.inspect("LEFT", "receiver_ready")

            # Approach source_1 from left_wait, then immediately grasp part_1.
            await robot.move("LEFT", "source_1")
            await robot.grasp("LEFT", "part_1")

            # Carry part_1 to buffer_1 (buffer entry requires buffer_lock).
            await robot.acquire("LEFT", "buffer_lock", 5.0)
            try:
                await robot.move("LEFT", "buffer_1")
                await robot.release("LEFT", "part_1", "buffer_1")
                # Immediately depart after release (same coroutine).
                await robot.move("LEFT", "left_wait")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")

            # Publish ready_1 for part_1.
            receipt1 = robot.signal("ready_1", "part_1")
            state["ready_receipts"]["part_1"] = receipt1

            # Return to home.
            await robot.move("LEFT", "left_home")
        finally:
            await robot.release_resource("LEFT", "tool")

    # ------------------------------------------------------------------
    # Consumer (RIGHT arm)
    # ------------------------------------------------------------------
    async def consumer() -> None:
        # ---- Consume part_0 ----
        # Wait for ready_0 receipt.
        ready0 = await robot.wait_event("ready_0", 10.0)
        state["ready_receipts"]["part_0"] = ready0

        # Approach buffer_0 from right_home, then immediately grasp part_0.
        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", "buffer_0")
        await robot.grasp("RIGHT", "part_0")

        # Carry part_0 to target_0, supplying the exact active ready receipt.
        await robot.move("RIGHT", "target_0", receipt=ready0)

        # Clear ready_0 after the carried move completes.
        robot.clear_event("ready_0", expected_version=ready0.version)

        # Release on target and depart before publishing empty_0.
        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_wait")

        # Publish empty_0 (buffer is now empty).
        empty_receipt = robot.signal("empty_0")
        state["empty_receipt"] = empty_receipt

        # ---- Consume part_1 ----
        # Wait for ready_1 receipt.
        ready1 = await robot.wait_event("ready_1", 10.0)
        state["ready_receipts"]["part_1"] = ready1

        # Approach buffer_1 from right_wait, then immediately grasp part_1.
        await robot.move("RIGHT", "buffer_1")
        await robot.grasp("RIGHT", "part_1")

        # Carry part_1 to target_1, supplying the exact active ready receipt.
        await robot.move("RIGHT", "target_1", receipt=ready1)

        # Clear ready_1 after the carried move completes.
        robot.clear_event("ready_1", expected_version=ready1.version)

        # Release on target and depart.
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home")

    # ------------------------------------------------------------------
    # Run producer and consumer concurrently.
    # ------------------------------------------------------------------
    await asyncio.gather(producer(), consumer())
