import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Shared state for producer/consumer coordination.
    state: dict = {
        "ready_receipt": None,   # EventReceipt for the currently active ready event
        "ready_item": None,      # "part_0" or "part_1"
        "empty_receipt": None,  # EventReceipt for empty_0
    }

    async def producer_part(part: str, source: str, ready_event: str) -> None:
        """LEFT arm: pick part from source, place at buffer, depart, publish ready."""
        # LEFT owns tool from before each source pickup through ready publication.
        await robot.acquire("LEFT", "tool", 5)
        await robot.set_mode("LEFT", "tool", "OFF")

        # Approach source from left_home, then immediately grasp.
        await robot.move("LEFT", source, receipt=None)
        await robot.grasp("LEFT", part, observation=None)

        # Carry part to buffer.
        await robot.move("LEFT", "buffer_0", receipt=None)

        # Release on buffer, then immediately depart.
        await robot.release("LEFT", part, "buffer_0")
        await robot.move("LEFT", "left_home", receipt=None)

        # Release tool on every exit.
        await robot.set_mode("LEFT", "tool", "OFF")
        await robot.release_resource("LEFT", "tool")

        # Publish ready after departing.
        receipt = robot.signal(ready_event, part)
        state["ready_receipt"] = receipt
        state["ready_item"] = part

    async def consumer_part(part: str, ready_event: str, target: str) -> None:
        """RIGHT arm: wait ready, pick from buffer, carry to target, clear ready,
        release on target, depart, publish empty_0."""
        # Wait for the corresponding ready receipt.
        receipt = await robot.wait_event(ready_event, 30)

        # Pick up from buffer using the matching approach sequence.
        buffer_pose = "buffer_0" if part == "part_0" else "buffer_1"
        start_pose = "right_home" if part == "part_0" else "right_wait"
        await robot.move("RIGHT", start_pose, receipt=None)
        await robot.move("RIGHT", buffer_pose, receipt=None)
        await robot.grasp("RIGHT", part, observation=None)

        # Carry to target, supplying the exact active item receipt.
        await robot.move("RIGHT", target, receipt=receipt)

        # Clear ready after the carried move completes.
        robot.clear_event(ready_event, expected_version=receipt.version)

        # Release on target, then immediately depart.
        await robot.release("RIGHT", part, target)
        await robot.move("RIGHT", "right_home", receipt=None)

        # Publish empty_0 after departing.
        empty_receipt = robot.signal("empty_0", None)
        state["empty_receipt"] = empty_receipt

    async def episode(part: str, source: str, ready_event: str, target: str) -> None:
        """One complete producer/consumer episode for a part."""
        producer = asyncio.create_task(
            producer_part(part, source, ready_event)
        )
        consumer = asyncio.create_task(
            consumer_part(part, ready_event, target)
        )
        await producer
        await consumer

        # Producer waits and clears empty_0 before entering buffer with next part.
        empty_receipt = state["empty_receipt"]
        await robot.wait_event("empty_0", 30)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)
        state["empty_receipt"] = None
        state["ready_receipt"] = None
        state["ready_item"] = None

    # Episode 1: part_0 from source_0 to target_0.
    await episode("part_0", "source_0", "ready_0", "target_0")

    # Episode 2: part_1 from source_1 to target_1.
    # For item 1, wait and clear empty_0, then inspect both readiness facts.
    await robot.wait_event("empty_0", 30)
    empty_receipt = state["empty_receipt"]
    if empty_receipt is not None:
        robot.clear_event("empty_0", expected_version=empty_receipt.version)
        state["empty_receipt"] = None

    # Inspect both readiness facts (serial checks in this SERIAL variant).
    await robot.inspect("RIGHT", "line_clear")
    await robot.inspect("RIGHT", "receiver_ready")

    # Proceed with part_1 episode (empty_0 already cleared above).
    await episode_part1("part_1", "source_1", "ready_1", "target_1", robot, state)


async def episode_part1(
    part: str,
    source: str,
    ready_event: str,
    target: str,
    robot: Robot,
    state: dict,
) -> None:
    """Episode for part_1, assuming empty_0 already cleared."""
    # LEFT owns tool from before source pickup through ready publication.
    await robot.acquire("LEFT", "tool", 5)
    await robot.set_mode("LEFT", "tool", "OFF")

    # Approach source_1 from left_wait, then immediately grasp.
    await robot.move("LEFT", "left_wait", receipt=None)
    await robot.grasp("LEFT", part, observation=None)

    # Carry to buffer.
    await robot.move("LEFT", "buffer_1", receipt=None)

    # Release on buffer, then immediately depart.
    await robot.release("LEFT", part, "buffer_1")
    await robot.move("LEFT", "left_home", receipt=None)

    # Release tool on exit.
    await robot.set_mode("LEFT", "tool", "OFF")
    await robot.release_resource("LEFT", "tool")

    # Publish ready_1.
    receipt = robot.signal(ready_event, part)
    state["ready_receipt"] = receipt
    state["ready_item"] = part

    # Consumer: wait ready_1, pick from buffer_1, carry to target_1.
    ready_receipt = await robot.wait_event(ready_event, 30)
    await robot.move("RIGHT", "right_wait", receipt=None)
    await robot.move("RIGHT", "buffer_1", receipt=None)
    await robot.grasp("RIGHT", part, observation=None)
    await robot.move("RIGHT", target, receipt=ready_receipt)
    robot.clear_event(ready_event, expected_version=ready_receipt.version)
    await robot.release("RIGHT", part, target)
    await robot.move("RIGHT", "right_home", receipt=None)

    # Publish empty_0.
    empty_receipt = robot.signal("empty_0", None)
    state["empty_receipt"] = empty_receipt

    # Producer waits and clears empty_0.
    await robot.wait_event("empty_0", 30)
    robot.clear_event("empty_0", expected_version=empty_receipt.version)
    state["empty_receipt"] = None
    state["ready_receipt"] = None
    state["ready_item"] = None
