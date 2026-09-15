import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # LONG variant: LEFT acquires tool before source pickup and keeps it across
    # the second-item wait and checks. Release tool on every normal, failure and
    # cancellation exit.

    tool_acquired = False
    buffer_lock_held = False

    async def acquire_tool():
        nonlocal tool_acquired
        await robot.acquire("LEFT", "tool", 5)
        tool_acquired = True

    async def release_tool():
        nonlocal tool_acquired
        if tool_acquired:
            try:
                await robot.set_mode("LEFT", "tool", "OFF")
            except Exception:
                pass
            try:
                await robot.release_resource("LEFT", "tool")
            except Exception:
                pass
            tool_acquired = False

    async def acquire_buffer_lock():
        nonlocal buffer_lock_held
        await robot.acquire("LEFT", "buffer_lock", 5)
        buffer_lock_held = True

    async def release_buffer_lock():
        nonlocal buffer_lock_held
        if buffer_lock_held:
            try:
                await robot.release_resource("LEFT", "buffer_lock")
            except Exception:
                pass
            buffer_lock_held = False

    async def producer_episode(item_id: str, source_pose: str, buffer_pose: str,
                               ready_event: str, is_second: bool):
        # Approach source from left_home (item 0) or left_wait (item 1)
        start_pose = "left_home" if not is_second else "left_wait"
        await robot.move("LEFT", start_pose)
        await robot.move("LEFT", source_pose)
        await robot.grasp("LEFT", item_id)
        # Carry to buffer
        await robot.move("LEFT", buffer_pose)
        # Both participants own buffer_lock during buffer entry and departure.
        await acquire_buffer_lock()
        await robot.release("LEFT", item_id, buffer_pose)
        # Immediately depart
        await robot.move("LEFT", "left_wait")
        await release_buffer_lock()
        # Publish ready
        robot.signal(ready_event, item_id)

    async def consumer_episode(item_id: str, buffer_pose: str, target_pose: str,
                               ready_event: str, is_second: bool):
        # Wait for ready receipt
        receipt = await robot.wait_event(ready_event, 10)
        # Approach buffer from right_home (item 0) or right_wait (item 1)
        start_pose = "right_home" if not is_second else "right_wait"
        await robot.move("RIGHT", start_pose)
        await robot.move("RIGHT", buffer_pose)
        await robot.grasp("RIGHT", item_id)
        # Carry to target with the exact active item receipt
        await robot.move("RIGHT", target_pose, receipt=receipt)
        # Clear ready after carried move
        robot.clear_event(ready_event, expected_version=receipt.version)
        # Release on target and depart
        await robot.release("RIGHT", item_id, target_pose)
        await robot.move("RIGHT", "right_wait")
        # Publish empty
        robot.signal("empty_0", item_id)

    async def second_item_checks():
        # D4 joins the two second-item checks with asyncio.gather
        obs_left, obs_right = await asyncio.gather(
            robot.inspect("LEFT", "line_clear"),
            robot.inspect("RIGHT", "receiver_ready"),
        )
        return obs_left, obs_right

    try:
        # LONG: acquire tool before source pickup
        await acquire_tool()

        # Episode 1: part_0
        await producer_episode("part_0", "source_0", "buffer_0", "ready_0", False)
        await consumer_episode("part_0", "buffer_0", "target_0", "ready_0", False)

        # Second item: wait and clear empty_0 before entering buffer with part_1
        empty_receipt = await robot.wait_event("empty_0", 10)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

        # D4: join second-item checks with asyncio.gather inside i == 1 branch
        obs_left, obs_right = await second_item_checks()
        # Both public Boolean fields must permit transfer
        left_val = obs_left.value
        right_val = obs_right.value
        if not (isinstance(left_val, dict) and left_val.get("clear") is True):
            raise ContractError("line_clear not clear")
        if not (isinstance(right_val, dict) and right_val.get("ready") is True):
            raise ContractError("receiver_ready not ready")

        # Episode 2: part_1
        await producer_episode("part_1", "source_1", "buffer_1", "ready_1", True)
        await consumer_episode("part_1", "buffer_1", "target_1", "ready_1", True)

        # Return arms to homes
        await robot.move("LEFT", "left_home")
        await robot.move("RIGHT", "right_home")

    finally:
        await release_buffer_lock()
        await release_tool()
