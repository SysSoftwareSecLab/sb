import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # LONG variant: LEFT acquires tool before source pickup and keeps it across
    # the second-item wait and checks. Release tool on every normal exit.
    #
    # Layout LH: two items cross a capacity-one buffer from LEFT producer to
    # RIGHT consumer. buffer_0 and buffer_1 are the same physical capacity-one
    # buffer at identical coordinates with item-specific pickup contracts.
    #
    # A alternates complete producer/consumer episodes; B runs producer and
    # consumer coroutines together. We implement B: producer and consumer
    # coroutines run together.

    # Acquire tool on LEFT before source pickup (LONG).
    await robot.acquire("LEFT", "tool", timeout_s=5.0)

    try:
        # ---- Episode for part_0 ----
        # Producer: LEFT picks part_0 from source_0, places at buffer_0, departs.
        # Approach sequence: LEFT start left_home -> source_0, grasp part_0.
        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "source_0")
        await robot.grasp("LEFT", "part_0")

        # Acquire buffer_lock for buffer entry.
        await robot.acquire("LEFT", "buffer_lock", timeout_s=5.0)
        try:
            # Move to buffer_0 and release part_0.
            await robot.move("LEFT", "buffer_0")
            await robot.release("LEFT", "part_0", "buffer_0")
            # Immediately depart before ready publication.
            await robot.move("LEFT", "left_wait")
        finally:
            await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready_0 for part_0.
        ready0 = robot.signal("ready_0", "part_0")

        # Consumer: RIGHT waits ready_0, picks part_0 from buffer_0, carries to
        # target_0 with the exact active item receipt, releases, departs, then
        # clears ready_0.
        # Approach sequence: RIGHT start right_home -> buffer_0, grasp part_0.
        await robot.move("RIGHT", "right_home")

        # Wait for ready_0 receipt.
        ready0_receipt = await robot.wait_event("ready_0", timeout_s=5.0)

        # Acquire buffer_lock for buffer entry.
        await robot.acquire("RIGHT", "buffer_lock", timeout_s=5.0)
        try:
            # Move to buffer_0 and grasp part_0.
            await robot.move("RIGHT", "buffer_0")
            await robot.grasp("RIGHT", "part_0")
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")

        # Carried move to target_0 with the exact active item receipt.
        await robot.move("RIGHT", "target_0", receipt=ready0_receipt)
        await robot.release("RIGHT", "part_0", "target_0")
        # Depart before publishing empty_0.
        await robot.move("RIGHT", "right_wait")

        # Clear ready_0 after carried move completes.
        robot.clear_event("ready_0", expected_version=ready0_receipt.version)

        # Publish empty_0.
        empty0 = robot.signal("empty_0")

        # ---- Episode for part_1 ----
        # Producer: LEFT waits and clears empty_0 before entering buffer with
        # the second part. LONG: tool already held across wait and checks.
        empty0_receipt = await robot.wait_event("empty_0", timeout_s=5.0)
        robot.clear_event("empty_0", expected_version=empty0_receipt.version)

        # Second-item checks: inspect line_clear with LEFT and receiver_ready
        # with RIGHT; both public Boolean fields must permit transfer.
        # D3 performs the two second-item checks serially.
        line_clear_obs = await robot.inspect("LEFT", "line_clear")
        receiver_ready_obs = await robot.inspect("RIGHT", "receiver_ready")

        # Verify both checks permit transfer.
        line_clear_val = line_clear_obs.value
        receiver_ready_val = receiver_ready_obs.value
        if not (isinstance(line_clear_val, dict) and line_clear_val.get("clear") is True):
            raise ContractError("line_clear does not permit transfer")
        if not (isinstance(receiver_ready_val, dict) and receiver_ready_val.get("ready") is True):
            raise ContractError("receiver_ready does not permit transfer")

        # Producer: LEFT picks part_1 from source_1, places at buffer_1, departs.
        # Approach sequence: LEFT start left_wait -> source_1, grasp part_1.
        await robot.move("LEFT", "left_wait")
        await robot.move("LEFT", "source_1")
        await robot.grasp("LEFT", "part_1")

        # Acquire buffer_lock for buffer entry.
        await robot.acquire("LEFT", "buffer_lock", timeout_s=5.0)
        try:
            # Move to buffer_1 and release part_1.
            await robot.move("LEFT", "buffer_1")
            await robot.release("LEFT", "part_1", "buffer_1")
            # Immediately depart before ready publication.
            await robot.move("LEFT", "left_home")
        finally:
            await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready_1 for part_1.
        ready1 = robot.signal("ready_1", "part_1")

        # Consumer: RIGHT waits ready_1, picks part_1 from buffer_1, carries to
        # target_1 with the exact active item receipt, releases, departs, then
        # clears ready_1.
        # Approach sequence: RIGHT start right_wait -> buffer_1, grasp part_1.
        await robot.move("RIGHT", "right_wait")

        # Wait for ready_1 receipt.
        ready1_receipt = await robot.wait_event("ready_1", timeout_s=5.0)

        # Acquire buffer_lock for buffer entry.
        await robot.acquire("RIGHT", "buffer_lock", timeout_s=5.0)
        try:
            # Move to buffer_1 and grasp part_1.
            await robot.move("RIGHT", "buffer_1")
            await robot.grasp("RIGHT", "part_1")
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")

        # Carried move to target_1 with the exact active item receipt.
        await robot.move("RIGHT", "target_1", receipt=ready1_receipt)
        await robot.release("RIGHT", "part_1", "target_1")
        # Depart before publishing empty_0.
        await robot.move("RIGHT", "right_home")

        # Clear ready_1 after carried move completes.
        robot.clear_event("ready_1", expected_version=ready1_receipt.version)

        # Publish empty_0 (buffer is now empty).
        robot.signal("empty_0")

        # Return arms to homes (already there, but ensure).
        await robot.move("LEFT", "left_home")
        await robot.move("RIGHT", "right_home")

    finally:
        # Release tool on every normal, failure and cancellation exit.
        try:
            await robot.release_resource("LEFT", "tool")
        except Exception:
            pass
