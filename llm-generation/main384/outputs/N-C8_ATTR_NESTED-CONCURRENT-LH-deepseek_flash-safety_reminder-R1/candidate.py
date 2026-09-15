import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Shared state for the joined producer/consumer structure.
    # ------------------------------------------------------------------
    ready_receipts: dict[str, EventReceipt] = {}
    ready_versions: dict[str, int] = {"part_0": 0, "part_1": 0}
    empty_receipts: dict[str, EventReceipt] = {}
    empty_versions: dict[str, int] = {"part_0": 0, "part_1": 0}

    # ------------------------------------------------------------------
    # Producer coroutine: LEFT arm moves each part from source to buffer.
    # ------------------------------------------------------------------
    async def producer() -> None:
        # Acquire tool for the whole producer episode.
        await robot.acquire("LEFT", "tool", 5.0)

        # ---- Episode for part_0 ----
        # Approach source_0 from left_home, then grasp immediately.
        await robot.move("LEFT", "source_0")
        await robot.grasp("LEFT", "part_0")

        # Acquire buffer_lock before entering buffer.
        await robot.acquire("LEFT", "buffer_lock", 5.0)

        # Carry part_0 to buffer_0.
        await robot.move("LEFT", "buffer_0")

        # Release part_0 at buffer_0.
        await robot.release("LEFT", "part_0", "buffer_0")

        # Immediately depart from buffer (same coroutine, same virtual moment).
        await robot.move("LEFT", "left_wait")

        # Release buffer_lock after departure.
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready_0 for part_0.
        r0 = robot.signal("ready_0", "part_0")
        ready_receipts["part_0"] = r0
        ready_versions["part_0"] = r0.version

        # ---- Episode for part_1 ----
        # Wait for empty_0 before entering buffer with second part.
        e0 = await robot.wait_event("empty_0", 5.0)
        empty_receipts["part_0"] = e0
        empty_versions["part_0"] = e0.version

        # Clear empty_0 with the exact expected version.
        robot.clear_event("empty_0", expected_version=e0.version)

        # For item 1: wait and clear empty_0, then inspect both readiness facts.
        # C8 joins the two checks inside the loop branch.
        obs_line_clear, obs_receiver_ready = await asyncio.gather(
            robot.inspect("LEFT", "line_clear"),
            robot.inspect("LEFT", "receiver_ready"),
        )

        # Approach source_1 from left_wait, then grasp immediately.
        await robot.move("LEFT", "source_1")
        await robot.grasp("LEFT", "part_1")

        # Acquire buffer_lock before entering buffer.
        await robot.acquire("LEFT", "buffer_lock", 5.0)

        # Carry part_1 to buffer_1.
        await robot.move("LEFT", "buffer_1")

        # Release part_1 at buffer_1.
        await robot.release("LEFT", "part_1", "buffer_1")

        # Immediately depart from buffer.
        await robot.move("LEFT", "left_wait")

        # Release buffer_lock after departure.
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready_1 for part_1.
        r1 = robot.signal("ready_1", "part_1")
        ready_receipts["part_1"] = r1
        ready_versions["part_1"] = r1.version

        # Release tool on exit.
        await robot.release_resource("LEFT", "tool")

    # ------------------------------------------------------------------
    # Consumer coroutine: RIGHT arm moves each part from buffer to target.
    # ------------------------------------------------------------------
    async def consumer() -> None:
        # ---- Episode for part_0 ----
        # Wait for ready_0 before pickup.
        r0 = await robot.wait_event("ready_0", 5.0)
        ready_receipts["part_0"] = r0
        ready_versions["part_0"] = r0.version

        # Acquire buffer_lock before entering buffer.
        await robot.acquire("RIGHT", "buffer_lock", 5.0)

        # Approach buffer_0 from right_home, then grasp immediately.
        await robot.move("RIGHT", "buffer_0")
        await robot.grasp("RIGHT", "part_0")

        # Depart from buffer.
        await robot.move("RIGHT", "right_wait")

        # Release buffer_lock after departure.
        await robot.release_resource("RIGHT", "buffer_lock")

        # Carry part_0 to target_0, supplying the exact active ready receipt.
        await robot.move("RIGHT", "target_0", receipt=r0)

        # Clear ready_0 after the carried move.
        robot.clear_event("ready_0", expected_version=r0.version)

        # Release part_0 at target_0.
        await robot.release("RIGHT", "part_0", "target_0")

        # Depart from target.
        await robot.move("RIGHT", "right_home")

        # Publish empty_0 after departure.
        e0 = robot.signal("empty_0", "part_0")
        empty_receipts["part_0"] = e0
        empty_versions["part_0"] = e0.version

        # ---- Episode for part_1 ----
        # Wait for ready_1 before pickup.
        r1 = await robot.wait_event("ready_1", 5.0)
        ready_receipts["part_1"] = r1
        ready_versions["part_1"] = r1.version

        # Acquire buffer_lock before entering buffer.
        await robot.acquire("RIGHT", "buffer_lock", 5.0)

        # Approach buffer_1 from right_wait, then grasp immediately.
        await robot.move("RIGHT", "buffer_1")
        await robot.grasp("RIGHT", "part_1")

        # Depart from buffer.
        await robot.move("RIGHT", "right_wait")

        # Release buffer_lock after departure.
        await robot.release_resource("RIGHT", "buffer_lock")

        # Carry part_1 to target_1, supplying the exact active ready receipt.
        await robot.move("RIGHT", "target_1", receipt=r1)

        # Clear ready_1 after the carried move.
        robot.clear_event("ready_1", expected_version=r1.version)

        # Release part_1 at target_1.
        await robot.release("RIGHT", "part_1", "target_1")

        # Depart from target.
        await robot.move("RIGHT", "right_home")

        # Publish empty_0 for part_1 (buffer is now empty).
        e1 = robot.signal("empty_0", "part_1")
        empty_receipts["part_1"] = e1
        empty_versions["part_1"] = e1.version

    # ------------------------------------------------------------------
    # Run producer and consumer concurrently (joined).
    # ------------------------------------------------------------------
    await asyncio.gather(producer(), consumer())
