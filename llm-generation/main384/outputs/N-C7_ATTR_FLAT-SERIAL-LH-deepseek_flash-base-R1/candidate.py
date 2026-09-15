from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Task C7_ATTR_FLAT-SERIAL-LH
    # Two parts cross a capacity-one buffer from LEFT producer to RIGHT
    # consumer.  Structure is SERIAL: complete producer/consumer episodes
    # alternate.  LEFT owns the tool from before each source pickup
    # through ready publication and releases it on every exit.
    # ------------------------------------------------------------------

    # ---- helpers -----------------------------------------------------

    async def producer_episode(item_id: str, source_pose: str,
                               buffer_pose: str, ready_event: str) -> None:
        """LEFT: acquire tool, pick item from source, place at buffer,
        publish ready, release tool."""
        # Acquire the tool before source pickup.
        await robot.acquire("LEFT", "tool", 5.0)

        # Approach source from left_home (part_0) or left_wait (part_1).
        start_pose = "left_home" if item_id == "part_0" else "left_wait"
        await robot.move("LEFT", start_pose)
        # Approach must be immediately followed by grasp in the same
        # coroutine at the same virtual instant.
        await robot.grasp("LEFT", item_id)

        # Carry to buffer.  buffer_0 and buffer_1 are the same physical
        # capacity-one buffer at identical coordinates.
        await robot.move("LEFT", buffer_pose)

        # Enter buffer under lock.
        await robot.acquire("LEFT", "buffer_lock", 5.0)
        await robot.release("LEFT", item_id, buffer_pose)
        # Depart immediately after release (same coroutine).
        await robot.move("LEFT", "left_wait")
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready for this item.
        robot.signal(ready_event)

        # Release tool on exit.
        await robot.release_resource("LEFT", "tool")

    async def consumer_episode(item_id: str, buffer_pose: str,
                               target_pose: str, ready_event: str) -> None:
        """RIGHT: wait ready, pick from buffer, carry to target,
        release, clear ready, publish empty."""
        # Wait for the ready receipt for this item.
        receipt = await robot.wait_event(ready_event, 10.0)

        # Approach buffer from right_home (part_0) or right_wait (part_1).
        start_pose = "right_home" if item_id == "part_0" else "right_wait"
        await robot.move("RIGHT", start_pose)
        # Approach must be immediately followed by grasp.
        await robot.grasp("RIGHT", item_id)

        # Enter buffer under lock and pick up.
        await robot.acquire("RIGHT", "buffer_lock", 5.0)
        # (grasp already done above; here we just depart with the item)
        await robot.move("RIGHT", target_pose)
        await robot.release("RIGHT", item_id, target_pose)
        await robot.move("RIGHT", "right_wait")
        await robot.release_resource("RIGHT", "buffer_lock")

        # Clear ready after the carried move (move to target completed).
        robot.clear_event(ready_event, expected_version=receipt.version)

        # Publish empty after departing.
        robot.signal("empty_0")

    # ---- serial alternating episodes ---------------------------------
    # Episode 1: part_0
    await producer_episode("part_0", "source_0", "buffer_0", "ready_0")
    await consumer_episode("part_0", "buffer_0", "target_0", "ready_0")

    # Episode 2: part_1
    # For item 1, wait and clear empty_0 before entering buffer.
    empty_receipt = await robot.wait_event("empty_0", 10.0)
    robot.clear_event("empty_0", expected_version=empty_receipt.version)

    # Inspect both readiness facts serially (C7 checks serially).
    await robot.inspect("LEFT", "line_clear")
    await robot.inspect("LEFT", "receiver_ready")

    await producer_episode("part_1", "source_1", "buffer_1", "ready_1")
    await consumer_episode("part_1", "buffer_1", "target_1", "ready_1")

    # ---- final: return arms to homes ---------------------------------
    await robot.move("LEFT", "left_home")
    await robot.move("RIGHT", "right_home")
