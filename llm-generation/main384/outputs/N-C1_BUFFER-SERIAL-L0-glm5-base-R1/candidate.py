import asyncio
from bridge_robot_api import Robot


async def _producer_episode_a(robot: Robot, part_id: str, source_pose: str,
                              buffer_pose: str, ready_event: str,
                              empty_event: str, left_wait_pose: str) -> None:
    """Producer A: grasp part at source, place at buffer, depart, publish ready."""
    # Approach source and immediately grasp.
    await robot.move("LEFT", source_pose)
    await robot.grasp("LEFT", part_id)

    # Acquire buffer lock for entry.
    await robot.acquire("LEFT", "buffer_lock", 5)

    # Move carried part to buffer.
    await robot.move("LEFT", buffer_pose)

    # Release part onto buffer support zone.
    await robot.release("LEFT", part_id, buffer_pose)

    # Immediate separating departure from buffer.
    await robot.move("LEFT", left_wait_pose)

    # Release lock after departure.
    await robot.release_resource("LEFT", "buffer_lock")

    # Publish ready receipt for consumer's carried move.
    robot.signal(ready_event, part_id)

    # Wait for consumer to clear ready after its carried move.
    await robot.wait_event(ready_event, 30)
    robot.clear_event(ready_event, expected_version=2)

    # Wait for empty_0 before entering buffer with second part (caller chains).
    await robot.wait_event(empty_event, 30)
    robot.clear_event(empty_event, expected_version=2)


async def _consumer_episode_a(robot: Robot, part_id: str, buffer_pose: str,
                              target_pose: str, right_wait_pose: str,
                              ready_event: str, empty_event: str,
                              is_last: bool) -> None:
    """Consumer A: wait ready, pickup from buffer, carry to target, depart, publish empty."""
    # Wait for producer's ready receipt.
    receipt = await robot.wait_event(ready_event, 30)

    # Acquire buffer lock for entry.
    await robot.acquire("RIGHT", "buffer_lock", 5)

    # Approach buffer and immediately grasp.
    await robot.move("RIGHT", buffer_pose)
    await robot.grasp("RIGHT", part_id, observation=None)

    # Carry part to target using the exact active item receipt.
    await robot.move("RIGHT", target_pose, receipt=receipt)

    # Clear ready after carried move completes.
    robot.clear_event(ready_event, expected_version=receipt.version)

    # Release part on target support zone.
    await robot.release("RIGHT", part_id, target_pose)

    # Immediate separating departure from target.
    await robot.move("RIGHT", right_wait_pose)

    # Release lock after departure.
    await robot.release_resource("RIGHT", "buffer_lock")

    # Publish empty_0 after departure.
    robot.signal(empty_event, part_id)

    if not is_last:
        # Producer waits for and clears empty_0 before second part.
        await robot.wait_event(empty_event, 30)
        robot.clear_event(empty_event, expected_version=2)


async def _producer_b(robot: Robot) -> None:
    """B producer coroutine: both parts sequentially."""
    await robot.move("LEFT", "source_0")
    await robot.grasp("LEFT", "part_0")

    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", "buffer_0")
    await robot.release("LEFT", "part_0", "buffer_0")
    await robot.move("LEFT", "left_wait")
    await robot.release_resource("LEFT", "buffer_lock")

    robot.signal("ready_0", "part_0")
    await robot.wait_event("ready_0", 30)
    robot.clear_event("ready_0", expected_version=2)

    await robot.wait_event("empty_0", 30)
    robot.clear_event("empty_0", expected_version=2)

    await robot.move("LEFT", "source_1")
    await robot.grasp("LEFT", "part_1")

    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", "buffer_1")
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_wait")
    await robot.release_resource("LEFT", "buffer_lock")

    robot.signal("ready_1", "part_1")
    await robot.wait_event("ready_1", 30)
    robot.clear_event("ready_1", expected_version=2)

    await robot.move("LEFT", "left_home")


async def _consumer_b(robot: Robot) -> None:
    """B consumer coroutine: both parts sequentially."""
    r0 = await robot.wait_event("ready_0", 30)
    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", "buffer_0")
    await robot.grasp("RIGHT", "part_0", observation=None)
    await robot.move("RIGHT", "target_0", receipt=r0)
    robot.clear_event("ready_0", expected_version=r0.version)
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_wait")
    await robot.release_resource("RIGHT", "buffer_lock")

    robot.signal("empty_0", "part_0")
    await robot.wait_event("empty_0", 30)
    robot.clear_event("empty_0", expected_version=2)

    r1 = await robot.wait_event("ready_1", 30)
    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", "buffer_1")
    await robot.grasp("RIGHT", "part_1", observation=None)
    await robot.move("RIGHT", "target_1", receipt=r1)
    robot.clear_event("ready_1", expected_version=r1.version)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")


async def run_task(robot: Robot) -> None:
    """Implement C1_BUFFER-SERIAL-L0 variant A.

    Variant A alternates complete producer/consumer episodes:
    part_0 full cycle, then part_1 full cycle. Each cycle:
    producer places at buffer, departs, publishes ready; consumer
    waits ready, picks up, carries to target with exact receipt,
    clears ready, releases on target, departs, publishes empty_0.
    """
    # Episode 1: part_0
    await _producer_episode_a(robot, "part_0", "source_0", "buffer_0",
                              "ready_0", "empty_0", "left_wait")
    await _consumer_episode_a(robot, "part_0", "buffer_0", "target_0",
                              "right_wait", "ready_0", "empty_0", is_last=False)

    # Episode 2: part_1
    await _producer_episode_a(robot, "part_1", "source_1", "buffer_1",
                              "ready_1", "empty_0", "left_wait")
    await _consumer_episode_a(robot, "part_1", "buffer_1", "target_1",
                              "right_wait", "ready_1", "empty_0", is_last=True)
