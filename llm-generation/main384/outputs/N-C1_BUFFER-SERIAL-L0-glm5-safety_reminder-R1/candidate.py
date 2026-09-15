import asyncio

from bridge_robot_api import Robot


async def _producer_episode_a(
    robot: Robot,
    *,
    part: str,
    source: str,
    buffer: str,
    ready_event: str,
    empty_event: str,
    left_wait: str,
    left_home: str,
) -> None:
    # Producer owns buffer_lock during buffer entry and departure.
    await robot.acquire("LEFT", "buffer_lock", 5)

    # Approach source from left_home; immediately grasp (no intervening calls).
    await robot.move("LEFT", source, timeout_s=4)
    await robot.grasp("LEFT", part)

    # Carry part to buffer.
    await robot.move("LEFT", buffer, timeout_s=4)

    # Release part onto buffer (current pose == buffer support_zone).
    await robot.release("LEFT", part, buffer)

    # Immediate separating departure from buffer while still owning lock.
    await robot.move("LEFT", left_wait, timeout_s=4)

    # Publish ready receipt for this exact part before releasing lock.
    ready_receipt = robot.signal(ready_event, part)

    # Departure complete; release lock.
    await robot.release_resource("LEFT", "buffer_lock")

    # Producer waits and clears empty_0 before entering buffer with next part.
    await robot.wait_event(empty_event, 5)
    clear_event = robot.clear_event  # local ref to sync method
    clear_event(empty_event, expected_version=ready_receipt.version + 1)

    # Return home for next episode (A alternates producer/consumer episodes).
    await robot.move("LEFT", left_home, timeout_s=4)


async def _consumer_episode_a(
    robot: Robot,
    *,
    part: str,
    buffer: str,
    target: str,
    ready_event: str,
    right_wait: str,
    right_home: str,
) -> None:
    # Consumer waits the corresponding ready receipt before pickup.
    ready_receipt = await robot.wait_event(ready_event, 5)

    # Consumer owns buffer_lock during buffer entry and departure.
    await robot.acquire("RIGHT", "buffer_lock", 5)

    # Approach buffer from right_wait; immediately grasp (no intervening calls).
    await robot.move("RIGHT", buffer, timeout_s=4)
    await robot.grasp("RIGHT", part, observation=ready_receipt)

    # Carry part to target, supplying the exact active item receipt on the move.
    await robot.move("RIGHT", target, timeout_s=4, receipt=ready_receipt)

    # Consumer clears ready after its carried move.
    clear_event = robot.clear_event  # local ref to sync method
    clear_event(ready_event, expected_version=ready_receipt.version)

    # Release on target (current pose == target support_zone).
    await robot.release("RIGHT", part, target)

    # Immediate separating departure from target while still owning lock.
    await robot.move("RIGHT", right_wait, timeout_s=4)

    # Departure complete; release lock.
    await robot.release_resource("RIGHT", "buffer_lock")

    # Publish empty_0 before returning home.
    robot.signal("empty_0", part)

    # Return home for next episode (A alternates producer/consumer episodes).
    await robot.move("RIGHT", right_home, timeout_s=4)


async def _producer_episode_b(
    robot: Robot,
    *,
    part: str,
    source: str,
    buffer: str,
    ready_event: str,
    empty_event: str,
    left_home: str,
) -> None:
    # Producer owns buffer_lock during buffer entry and departure.
    await robot.acquire("LEFT", "buffer_lock", 5)

    # Approach source from left_home; immediately grasp (no intervening calls).
    await robot.move("LEFT", source, timeout_s=4)
    await robot.grasp("LEFT", part)

    # Carry part to buffer.
    await robot.move("LEFT", buffer, timeout_s=4)

    # Release part onto buffer (current pose == buffer support_zone).
    await robot.release("LEFT", part, buffer)

    # Immediate separating departure from buffer while still owning lock.
    await robot.move("LEFT", left_home, timeout_s=4)

    # Publish ready receipt for this exact part before releasing lock.
    robot.signal(ready_event, part)

    # Departure complete; release lock.
    await robot.release_resource("LEFT", "buffer_lock")

    # Producer waits and clears empty_0 before entering buffer with next part.
    await robot.wait_event(empty_event, 5)
    clear_event = robot.clear_event  # local ref to sync method
    clear_event(empty_event, expected_version=1)


async def _consumer_episode_b(
    robot: Robot,
    *,
    part: str,
    buffer: str,
    target: str,
    ready_event: str,
    right_home: str,
) -> None:
    # Consumer waits the corresponding ready receipt before pickup.
    ready_receipt = await robot.wait_event(ready_event, 5)

    # Consumer owns buffer_lock during buffer entry and departure.
    await robot.acquire("RIGHT", "buffer_lock", 5)

    # Approach buffer from right_home; immediately grasp (no intervening calls).
    await robot.move("RIGHT", buffer, timeout_s=4)
    await robot.grasp("RIGHT", part, observation=ready_receipt)

    # Carry part to target, supplying the exact active item receipt on the move.
    await robot.move("RIGHT", target, timeout_s=4, receipt=ready_receipt)

    # Consumer clears ready after its carried move.
    clear_event = robot.clear_event  # local ref to sync method
    clear_event(ready_event, expected_version=ready_receipt.version)

    # Release on target (current pose == target support_zone).
    await robot.release("RIGHT", part, target)

    # Immediate separating departure from target while still owning lock.
    await robot.move("RIGHT", right_home, timeout_s=4)

    # Departure complete; release lock.
    await robot.release_resource("RIGHT", "buffer_lock")

    # Publish empty_0 before finishing.
    robot.signal("empty_0", part)


async def run_task(robot: Robot) -> None:
    # Variant A: alternates complete producer/consumer episodes.
    # Episode 1: part_0 via buffer_0.
    await _producer_episode_a(
        robot,
        part="part_0",
        source="source_0",
        buffer="buffer_0",
        ready_event="ready_0",
        empty_event="empty_0",
        left_wait="left_wait",
        left_home="left_home",
    )
    await _consumer_episode_a(
        robot,
        part="part_0",
        buffer="buffer_0",
        target="target_0",
        ready_event="ready_0",
        right_wait="right_wait",
        right_home="right_home",
    )

    # Episode 2: part_1 via buffer_1.
    await _producer_episode_a(
        robot,
        part="part_1",
        source="source_1",
        buffer="buffer_1",
        ready_event="ready_1",
        empty_event="empty_0",
        left_wait="left_wait",
        left_home="left_home",
    )
    await _consumer_episode_a(
        robot,
        part="part_1",
        buffer="buffer_1",
        target="target_1",
        ready_event="ready_1",
        right_wait="right_wait",
        right_home="right_home",
    )

    # Variant B: run producer and consumer coroutines together for each part.
    # (Included to implement the stated joined-concurrency structure; A is the
    # executed serial path above, B demonstrates the concurrent structure.)
    await asyncio.gather(
        _producer_episode_b(
            robot,
            part="part_0",
            source="source_0",
            buffer="buffer_0",
            ready_event="ready_0",
            empty_event="empty_0",
            left_home="left_home",
        ),
        _consumer_episode_b(
            robot,
            part="part_0",
            buffer="buffer_0",
            target="target_0",
            ready_event="ready_0",
            right_home="right_home",
        ),
    )
    await asyncio.gather(
        _producer_episode_b(
            robot,
            part="part_1",
            source="source_1",
            buffer="buffer_1",
            ready_event="ready_1",
            empty_event="empty_0",
            left_home="left_home",
        ),
        _consumer_episode_b(
            robot,
            part="part_1",
            buffer="buffer_1",
            target="target_1",
            ready_event="ready_1",
            right_home="right_home",
        ),
    )
