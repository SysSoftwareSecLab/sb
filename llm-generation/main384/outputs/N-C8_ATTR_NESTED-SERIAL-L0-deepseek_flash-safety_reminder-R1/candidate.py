import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def left_producer(item_id: str, source_pose: str, buffer_pose: str,
                            ready_event: str, wait_empty: bool) -> None:
        # Acquire tool before source pickup
        await robot.acquire("LEFT", "tool", 5.0)

        # Approach source from left_home (or left_wait for item 1)
        start_pose = "left_home" if item_id == "part_0" else "left_wait"
        await robot.move("LEFT", start_pose)
        await robot.move("LEFT", source_pose)
        await robot.grasp("LEFT", item_id)

        # If second item, wait and clear empty_0 before entering buffer
        if wait_empty:
            receipt = await robot.wait_event("empty_0", 5.0)
            robot.clear_event("empty_0", expected_version=receipt.version)

        # Acquire buffer_lock, enter buffer, release, depart
        await robot.acquire("LEFT", "buffer_lock", 5.0)
        await robot.move("LEFT", buffer_pose)
        await robot.release("LEFT", item_id, buffer_pose)
        await robot.move("LEFT", "left_wait")
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready
        robot.signal(ready_event, item_id)

        # Release tool on exit
        await robot.release_resource("LEFT", "tool")

    async def right_consumer(item_id: str, buffer_pose: str, target_pose: str,
                             ready_event: str) -> None:
        # Wait for ready receipt
        receipt = await robot.wait_event(ready_event, 5.0)

        # Acquire buffer_lock, approach buffer, grasp, depart
        await robot.acquire("RIGHT", "buffer_lock", 5.0)
        await robot.move("RIGHT", "right_wait")
        await robot.move("RIGHT", buffer_pose)
        await robot.grasp("RIGHT", item_id)
        await robot.move("RIGHT", "right_wait")
        await robot.release_resource("RIGHT", "buffer_lock")

        # Carried move to target with the exact active receipt
        await robot.move("RIGHT", target_pose, receipt=receipt)

        # Clear ready after carried move
        robot.clear_event(ready_event, expected_version=receipt.version)

        # Release on target and depart
        await robot.release("RIGHT", item_id, target_pose)
        await robot.move("RIGHT", "right_home")

        # Publish empty
        robot.signal("empty_0", item_id)

    # ------------------------------------------------------------------
    # Episode 1: part_0
    # ------------------------------------------------------------------
    await left_producer("part_0", "source_0", "buffer_0", "ready_0", wait_empty=False)
    await right_consumer("part_0", "buffer_0", "target_0", "ready_0")

    # ------------------------------------------------------------------
    # Episode 2: part_1
    # ------------------------------------------------------------------
    # For item 1: wait and clear empty_0, then inspect both readiness facts
    # C8 joins the two checks inside the loop branch.
    empty_receipt = await robot.wait_event("empty_0", 5.0)
    robot.clear_event("empty_0", expected_version=empty_receipt.version)

    # Joined concurrency: run both inspections together
    obs_line, obs_receiver = await asyncio.gather(
        robot.inspect("LEFT", "line_clear"),
        robot.inspect("RIGHT", "receiver_ready"),
    )

    # Serial producer/consumer for part_1
    await left_producer("part_1", "source_1", "buffer_1", "ready_1", wait_empty=False)
    await right_consumer("part_1", "buffer_1", "target_1", "ready_1")
