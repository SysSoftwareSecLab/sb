import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    """
    C1_BUFFER-SERIAL-LH, variant A.

    A alternates complete producer/consumer episodes:
      - Episode 0: LEFT produces part_0 to buffer_0; RIGHT consumes part_0 to target_0.
      - Episode 1: LEFT produces part_1 to buffer_1; RIGHT consumes part_1 to target_1.

    Buffer is capacity-one (buffer_0 and buffer_1 name the same physical slot).
    Both participants own buffer_lock during buffer entry and departure.
    Producer places each part at buffer and immediately departs before ready publication.
    Consumer waits the corresponding ready receipt before pickup, and supplies that exact
    active item receipt on carried move to target. Consumer clears ready after its carried
    move, releases on target and departs before publishing empty_0. Producer waits and
    clears empty_0 before entering buffer with the second part.
    """

    # Episode 0: part_0 from source_0 -> buffer_0 -> target_0
    await _produce_episode(robot, part_id="part_0", source_pose="source_0",
                           buffer_pose="buffer_0", ready_event="ready_0",
                           left_wait_pose="left_wait", right_wait_pose="right_wait",
                           target_pose="target_0")
    await _consume_episode(robot, part_id="part_0", buffer_pose="buffer_0",
                           ready_event="ready_0", target_pose="target_0",
                           left_wait_pose="left_wait", right_wait_pose="right_wait",
                           empty_event="empty_0")

    # Episode 1: part_1 from source_1 -> buffer_1 -> target_1
    await _produce_episode(robot, part_id="part_1", source_pose="source_1",
                           buffer_pose="buffer_1", ready_event="ready_1",
                           left_wait_pose="left_wait", right_wait_pose="right_wait",
                           target_pose="target_1")
    await _consume_episode(robot, part_id="part_1", buffer_pose="buffer_1",
                           ready_event="ready_1", target_pose="target_1",
                           left_wait_pose="left_wait", right_wait_pose="right_wait",
                           empty_event="empty_0")


async def _produce_episode(robot: Robot, *, part_id: str, source_pose: str,
                           buffer_pose: str, ready_event: str,
                           left_wait_pose: str, right_wait_pose: str,
                           target_pose: str) -> None:
    """LEFT arm produces one part: source -> buffer, departs, publishes ready."""
    # LEFT starts at left_home; approach source from left_home and immediately grasp.
    await robot.move("LEFT", source_pose)
    await robot.grasp("LEFT", part_id)

    # Carry part to left_wait (staging pose before buffer entry).
    await robot.move("LEFT", left_wait_pose)

    # Acquire buffer_lock for buffer entry.
    await robot.acquire("LEFT", "buffer_lock", 5)

    # Enter buffer and release part there.
    await robot.move("LEFT", buffer_pose)
    await robot.release("LEFT", part_id, buffer_pose)

    # Depart immediately from buffer to left_wait (still owning lock during departure).
    await robot.move("LEFT", left_wait_pose)

    # Release buffer_lock after departure.
    await robot.release_resource("LEFT", "buffer_lock")

    # Return LEFT to home.
    await robot.move("LEFT", "left_home")

    # Publish ready event for this part (after departure).
    robot.signal(ready_event, part_id)


async def _consume_episode(robot: Robot, *, part_id: str, buffer_pose: str,
                           ready_event: str, target_pose: str,
                           left_wait_pose: str, right_wait_pose: str,
                           empty_event: str) -> None:
    """RIGHT arm consumes one part: wait ready -> buffer -> target, publish empty."""
    # RIGHT starts at right_home; move to right_wait staging pose.
    await robot.move("RIGHT", right_wait_pose)

    # Wait for the corresponding ready receipt before pickup.
    ready_receipt = await robot.wait_event(ready_event, 30)

    # Acquire buffer_lock for buffer entry.
    await robot.acquire("RIGHT", "buffer_lock", 5)

    # Enter buffer and grasp the part (approach from right_wait, immediately grasp).
    await robot.move("RIGHT", buffer_pose)
    await robot.grasp("RIGHT", part_id, observation=ready_receipt)

    # Depart immediately from buffer to right_wait (still owning lock during departure).
    await robot.move("RIGHT", right_wait_pose, receipt=ready_receipt)

    # Release buffer_lock after departure.
    await robot.release_resource("RIGHT", "buffer_lock")

    # Clear ready event after the carried move has completed.
    robot.clear_event(ready_event, expected_version=ready_receipt.version)

    # Carry part to target and release there.
    await robot.move("RIGHT", target_pose, receipt=ready_receipt)
    await robot.release("RIGHT", part_id, target_pose)

    # Depart immediately from target to right_wait.
    await robot.move("RIGHT", right_wait_pose)

    # Return RIGHT to home.
    await robot.move("RIGHT", "right_home")

    # Publish empty_0 (buffer empty) after departure.
    robot.signal(empty_event, None)

    # Producer (LEFT) waits and clears empty_0 before entering buffer with next part.
    empty_receipt = await robot.wait_event("empty_0", 30)
    robot.clear_event("empty_0", expected_version=empty_receipt.version)
