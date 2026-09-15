import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot):
    # Shared state between producer and consumer coroutines
    state = {
        "ready_receipts": {},   # item_id -> EventReceipt
        "empty_receipt": None,  # EventReceipt for empty_0
        "ready_cleared": {},    # item_id -> bool
        "empty_cleared": False,
        "producer_done": False,
        "consumer_done": False,
    }

    async def producer():
        # LEFT owns tool from before each source pickup through ready publication
        # and releases it on every exit.
        for idx, (item, source_pose, buffer_pose, ready_event) in enumerate([
            ("part_0", "source_0", "buffer_0", "ready_0"),
            ("part_1", "source_1", "buffer_1", "ready_1"),
        ]):
            # Acquire tool before source pickup
            await robot.acquire("LEFT", "tool", 5.0)

            # For item 1: wait and clear empty_0 before entering buffer with second part
            if idx == 1:
                # Wait for empty_0 signal from consumer
                empty_receipt = await robot.wait_event("empty_0", 10.0)
                state["empty_receipt"] = empty_receipt
                # Clear empty_0
                robot.clear_event("empty_0", expected_version=empty_receipt.version)
                state["empty_cleared"] = True

                # C8: join the two readiness checks inside the loop branch
                # Inspect both readiness facts concurrently
                obs_line_clear, obs_receiver_ready = await asyncio.gather(
                    robot.inspect("LEFT", "line_clear"),
                    robot.inspect("LEFT", "receiver_ready"),
                )

            # Move to source pose (approach start)
            await robot.move("LEFT", source_pose)

            # Approach: must immediately grasp after move completes
            # (same coroutine, same virtual moment)
            await robot.grasp("LEFT", item)

            # Move to buffer pose
            await robot.move("LEFT", buffer_pose)

            # Acquire buffer_lock before buffer entry
            await robot.acquire("LEFT", "buffer_lock", 5.0)

            # Release item at buffer
            await robot.release("LEFT", item, buffer_pose)

            # Depart buffer immediately (move away)
            await robot.move("LEFT", "left_wait")

            # Release buffer_lock after departure
            await robot.release_resource("LEFT", "buffer_lock")

            # Publish ready event
            receipt = robot.signal(ready_event, item_id=item)
            state["ready_receipts"][item] = receipt

            # Release tool on exit
            await robot.release_resource("LEFT", "tool")

        state["producer_done"] = True

    async def consumer():
        for idx, (item, buffer_pose, target_pose, ready_event) in enumerate([
            ("part_0", "buffer_0", "target_0", "ready_0"),
            ("part_1", "buffer_1", "target_1", "ready_1"),
        ]):
            # Wait for ready receipt
            ready_receipt = await robot.wait_event(ready_event, 10.0)
            state["ready_receipts"][item] = ready_receipt

            # Move to right_wait (approach start for buffer)
            await robot.move("RIGHT", "right_wait")

            # Acquire buffer_lock before buffer entry
            await robot.acquire("RIGHT", "buffer_lock", 5.0)

            # Move to buffer pose (approach interaction pose)
            await robot.move("RIGHT", buffer_pose)

            # Grasp item from buffer (immediate after approach)
            await robot.grasp("RIGHT", item)

            # Depart buffer immediately
            await robot.move("RIGHT", "right_wait")

            # Release buffer_lock after departure
            await robot.release_resource("RIGHT", "buffer_lock")

            # Carried move to target with the exact active item receipt
            await robot.move("RIGHT", target_pose, receipt=ready_receipt)

            # Clear ready after carried move completes
            robot.clear_event(ready_event, expected_version=ready_receipt.version)
            state["ready_cleared"][item] = True

            # Release on target
            await robot.release("RIGHT", item, target_pose)

            # Depart target
            await robot.move("RIGHT", "right_home")

            # Publish empty_0 after departure
            empty_receipt = robot.signal("empty_0")
            state["empty_receipt"] = empty_receipt

        state["consumer_done"] = True

    # Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())
