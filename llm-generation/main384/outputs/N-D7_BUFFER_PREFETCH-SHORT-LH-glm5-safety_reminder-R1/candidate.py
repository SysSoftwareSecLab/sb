import asyncio

from bridge_robot_api import Robot


async def _producer_episode(robot: Robot, part_id: str, source_pose: str,
                            buffer_pose: str, ready_event: str,
                            empty_event: str, empty_version: int) -> None:
    # Producer waits for empty_0 before entering buffer with the second part.
    if empty_version is not None:
        await robot.wait_event(empty_event, 120)
        await robot.clear_event(empty_event, expected_version=empty_version)

    # Approach source: start_pose left_home -> interaction_pose source.
    await robot.move("LEFT", source_pose)
    # Immediately grasp in the same virtual moment.
    await robot.grasp("LEFT", part_id)

    # Acquire buffer lock for buffer entry.
    await robot.acquire("LEFT", "buffer_lock", 120)

    # Move to buffer and place part.
    await robot.move("LEFT", buffer_pose)
    await robot.release("LEFT", part_id, buffer_pose)

    # Immediate separating departure from buffer.
    await robot.move("LEFT", "left_wait")

    # Publish ready receipt after departing buffer.
    receipt = robot.signal(ready_event)

    # Depart to home.
    await robot.move("LEFT", "left_home")

    # Release buffer lock after departure.
    await robot.release_resource("LEFT", "buffer_lock")

    # Keep the ready receipt active for the consumer's carried move.
    _ = receipt


async def _consumer_episode(robot: Robot, part_id: str, buffer_pose: str,
                             target_pose: str, ready_event: str,
                             start_pose: str, wait_pose: str,
                             home_pose: str) -> None:
    # Consumer waits the corresponding ready receipt before pickup.
    receipt = await robot.wait_event(ready_event, 120)

    # Acquire buffer lock for buffer entry.
    await robot.acquire("RIGHT", "buffer_lock", 120)

    # Approach buffer: start_pose -> interaction_pose buffer.
    await robot.move("RIGHT", buffer_pose)
    # Immediately grasp in the same virtual moment.
    await robot.grasp("RIGHT", part_id)

    # Carried move to target, supplying the exact active item receipt.
    await robot.move("RIGHT", target_pose, receipt=receipt)

    # Clear ready after the carried move.
    await robot.clear_event(ready_event, expected_version=receipt.version)

    # Release on target and depart before publishing empty_0.
    await robot.release("RIGHT", part_id, target_pose)
    await robot.move("RIGHT", wait_pose)

    # Publish empty_0 after departing target.
    robot.signal("empty_0")

    # Release buffer lock after departure.
    await robot.release_resource("RIGHT", "buffer_lock")

    # Return home.
    await robot.move("RIGHT", home_pose)


async def _producer_coroutine(robot: Robot) -> None:
    # Episode 1: part_0 from source_0 to buffer_0, publish ready_0.
    await _producer_episode(
        robot,
        part_id="part_0",
        source_pose="source_0",
        buffer_pose="buffer_0",
        ready_event="ready_0",
        empty_event="empty_0",
        empty_version=None,
    )

    # Episode 2: part_1 from source_1 to buffer_1, publish ready_1.
    # Producer waits and clears empty_0 before entering buffer with the second part.
    await _producer_episode(
        robot,
        part_id="part_1",
        source_pose="source_1",
        buffer_pose="buffer_1",
        ready_event="ready_1",
        empty_event="empty_0",
        empty_version=1,
    )


async def _consumer_coroutine(robot: Robot) -> None:
    # Episode 1: consume part_0 from buffer_0 to target_0, publish empty_0.
    await _consumer_episode(
        robot,
        part_id="part_0",
        buffer_pose="buffer_0",
        target_pose="target_0",
        ready_event="ready_0",
        start_pose="right_home",
        wait_pose="right_wait",
        home_pose="right_home",
    )

    # Episode 2: consume part_1 from buffer_1 to target_1, publish empty_0.
    await _consumer_episode(
        robot,
        part_id="part_1",
        buffer_pose="buffer_1",
        target_pose="target_1",
        ready_event="ready_1",
        start_pose="right_home",
        wait_pose="right_wait",
        home_pose="right_home",
    )


async def run_task(robot: Robot) -> None:
    producer = asyncio.create_task(_producer_coroutine(robot))
    consumer = asyncio.create_task(_consumer_coroutine(robot))
    await asyncio.gather(producer, consumer)
