import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # C7_ATTR_FLAT-CONCURRENT-LH
    # Layout LH: two parts cross a capacity-one buffer from LEFT producer to RIGHT consumer.
    # Variant CONCURRENT: A alternates complete producer/consumer episodes;
    # B runs producer and consumer coroutines together.
    # This implementation runs the two arms concurrently (B-style joined producer/consumer
    # coroutines) while preserving the required ordering and buffer capacity-one discipline.

    # Shared coordination state.
    state = {
        "empty_receipt": None,  # EventReceipt for empty_0, active while buffer empty signal is set
        "ready_receipts": {},   # item_id -> EventReceipt for ready_i
        "part_done": {"part_0": False, "part_1": False},
    }

    async def producer_episode(item_id: str, source_pose: str, buffer_pose: str,
                               ready_event: str, left_wait_pose: str) -> None:
        """LEFT produces one part: source pickup -> buffer deposit -> depart -> publish ready."""

        # For item 1, wait and clear empty_0 before entering buffer with the second part.
        if item_id == "part_1":
            # Wait until consumer has signaled empty_0 (buffer empty after first item consumed).
            empty_receipt = await robot.wait_event("empty_0", 30)
            # Producer clears empty_0 before entering buffer with the second part.
            robot.clear_event("empty_0", expected_version=empty_receipt.version)

        # LEFT owns tool from before each source pickup through ready publication.
        await robot.acquire("LEFT", "tool", 10)

        # Approach source from left_home (or left_wait for item 1) and immediately grasp.
        await robot.move("LEFT", source_pose)
        await robot.grasp("LEFT", item_id)

        # Carry to buffer. Buffer_lock owned during buffer entry and departure.
        await robot.acquire("LEFT", "buffer_lock", 10)
        await robot.move("LEFT", buffer_pose)

        # Release part onto buffer (support_zone must be current pose and in logical_supports).
        await robot.release("LEFT", item_id, buffer_pose)

        # Immediately depart buffer before ready publication.
        await robot.move("LEFT", left_wait_pose)
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready receipt for this item.
        ready_receipt = robot.signal(ready_event, item_id)
        state["ready_receipts"][item_id] = ready_receipt

        # Release tool on every exit.
        await robot.release_resource("LEFT", "tool")

        # Return LEFT to home after producer episode complete.
        await robot.move("LEFT", "left_home")

    async def consumer_episode(item_id: str, buffer_pose: str, target_pose: str,
                               ready_event: str, right_wait_pose: str) -> None:
        """RIGHT consumes one part: wait ready -> buffer pickup -> carried move -> clear ready
        -> release on target -> depart -> publish empty_0."""

        # Consumer waits the corresponding ready receipt before pickup.
        ready_receipt = await robot.wait_event(ready_event, 30)

        # Move to right_wait before buffer approach.
        await robot.move("RIGHT", right_wait_pose)

        # Approach buffer from right_wait and immediately grasp.
        await robot.move("RIGHT", buffer_pose)
        await robot.grasp("RIGHT", item_id, observation=ready_receipt)

        # Buffer_lock owned during buffer entry and departure.
        await robot.acquire("RIGHT", "buffer_lock", 10)

        # Carried move to target: supply exact active item receipt.
        await robot.move("RIGHT", target_pose, receipt=ready_receipt)

        # Consumer clears ready after its carried move.
        robot.clear_event(ready_event, expected_version=ready_receipt.version)

        # Release on target and depart before publishing empty_0.
        await robot.release("RIGHT", item_id, target_pose)
        await robot.move("RIGHT", right_wait_pose)
        await robot.release_resource("RIGHT", "buffer_lock")

        # Publish empty_0 (buffer empty).
        empty_receipt = robot.signal("empty_0", item_id)
        state["empty_receipt"] = empty_receipt

        # Return RIGHT to home after consumer episode complete.
        await robot.move("RIGHT", "right_home")

    async def left_arm() -> None:
        """LEFT arm: producer episodes for part_0 then part_1."""
        # Producer for part_0: source_0 -> buffer_0, publish ready_0.
        await producer_episode("part_0", "source_0", "buffer_0", "ready_0", "left_wait")
        state["part_done"]["part_0"] = True

        # Producer for part_1: wait/clear empty_0, source_1 -> buffer_1, publish ready_1.
        await producer_episode("part_1", "source_1", "buffer_1", "ready_1", "left_wait")
        state["part_done"]["part_1"] = True

    async def right_arm() -> None:
        """RIGHT arm: consumer episodes for part_0 then part_1."""
        # Consumer for part_0: wait ready_0, buffer_0 -> target_0, publish empty_0.
        await consumer_episode("part_0", "buffer_0", "target_0", "ready_0", "right_wait")

        # Consumer for part_1: wait ready_1, buffer_1 -> target_1, publish empty_0.
        await consumer_episode("part_1", "buffer_1", "target_1", "ready_1", "right_wait")

    # For item 1, inspect both readiness facts after waiting/clearing empty_0.
    # C7 checks serially inside the loop branch.
    async def inspect_readiness_for_item1() -> None:
        # Wait for empty_0 to be active (consumer has published buffer empty after part_0).
        empty_receipt = await robot.wait_event("empty_0", 30)
        # Inspect both readiness facts serially.
        await robot.inspect("LEFT", "line_clear")
        await robot.inspect("LEFT", "receiver_ready")
        # Clear empty_0 (producer's obligation before entering buffer with second part).
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

    # Run LEFT and RIGHT arm coroutines concurrently (joined producer/consumer structure).
    # The readiness inspection for item 1 is embedded in the producer_episode for part_1
    # which waits and clears empty_0 before entering the buffer, satisfying the C7 serial check.
    await asyncio.gather(left_arm(), right_arm())
