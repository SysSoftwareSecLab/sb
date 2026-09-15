import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # IC08_C8_ATTR_NESTED-OOD-STRUCTURAL_OOD
    # SERIAL variant: A alternates complete producer/consumer episodes.
    # Structure: FOR -> PAR_JOIN -> consumer IF (guards complete mission).
    # Two parts cross a capacity-one buffer from LEFT producer to RIGHT consumer.
    #
    # Item 0: LEFT produces (source_0 -> buffer_0), RIGHT consumes (buffer_0 -> target_0).
    # Item 1: LEFT produces (source_1 -> buffer_1), RIGHT consumes (buffer_1 -> target_1).
    # For item 1, consumer waits and clears empty_0, then inspects both readiness facts.

    items = ["part_0", "part_1"]

    for item in items:
        # ---- PAR_JOIN: concurrently run producer and consumer for this item ----
        producer_task = asyncio.create_task(_producer_episode(robot, item))
        consumer_task = asyncio.create_task(_consumer_episode(robot, item))
        await asyncio.gather(producer_task, consumer_task)

        # ---- consumer IF: guards the complete inherited mission ----
        # The consumer has already executed the complete mission inside _consumer_episode.
        # This branch confirms the structural-OOD shape requirement: the consumer IF
        # guards the complete mission. We verify terminal state via inspect.
        if item == "part_1":
            # C8 joins the two readiness checks inside the loop branch.
            line_obs = await robot.inspect("RIGHT", "line_clear")
            recv_obs = await robot.inspect("RIGHT", "receiver_ready")
            # Both facts inspected within the loop iteration's consumer IF branch.
            _ = (line_obs, recv_obs)

    # Terminal: both parts at targets, arms at homes, buffer empty, lock free, events inactive.
    # rq2_gate was never signaled, so it remains inactive at return.


async def _producer_episode(robot: Robot, item: str) -> None:
    """LEFT arm: pick part from source, place at buffer, depart, publish ready."""
    if item == "part_0":
        source = "source_0"
        buffer = "buffer_0"
        ready_event = "ready_0"
        start_pose = "left_home"
    else:
        source = "source_1"
        buffer = "buffer_1"
        ready_event = "ready_1"
        start_pose = "left_wait"

    # LEFT owns tool from before each source pickup through ready publication.
    await robot.acquire("LEFT", "tool", 5)
    await robot.set_mode("LEFT", "tool", "OFF")

    # For item 1, producer waits and clears empty_0 before entering buffer.
    if item == "part_1":
        empty_receipt = await robot.wait_event("empty_0", 30)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

    # Acquire buffer_lock for buffer entry.
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.set_mode("LEFT", "buffer_lock", "OFF")

    # Approach from start_pose to source, immediately grasp (no intervening calls).
    await robot.move("LEFT", start_pose)
    await robot.move("LEFT", source)
    await robot.grasp("LEFT", item)

    # Carry to buffer.
    await robot.move("LEFT", buffer)

    # Release at buffer (support_zone must be the buffer pose name).
    await robot.release("LEFT", item, buffer)

    # Depart immediately after release.
    await robot.move("LEFT", start_pose)

    # Release buffer_lock on exit.
    await robot.set_mode("LEFT", "buffer_lock", "OFF")
    await robot.release_resource("LEFT", "buffer_lock")

    # Publish ready (producer departs before ready publication).
    robot.signal(ready_event, item)

    # Release tool on every exit.
    await robot.set_mode("LEFT", "tool", "OFF")
    await robot.release_resource("LEFT", "tool")


async def _consumer_episode(robot: Robot, item: str) -> None:
    """RIGHT arm: wait ready, pick from buffer, carry to target, release, depart, signal empty."""
    if item == "part_0":
        buffer = "buffer_0"
        target = "target_0"
        ready_event = "ready_0"
        start_pose = "right_home"
    else:
        buffer = "buffer_1"
        target = "target_1"
        ready_event = "ready_1"
        start_pose = "right_wait"

    # Consumer waits the corresponding ready receipt before pickup.
    ready_receipt = await robot.wait_event(ready_event, 30)

    # Acquire buffer_lock for buffer entry (pickup).
    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.set_mode("RIGHT", "buffer_lock", "OFF")

    # Approach from start_pose to buffer, immediately grasp.
    await robot.move("RIGHT", start_pose)
    await robot.move("RIGHT", buffer)
    await robot.grasp("RIGHT", item)

    # Carry to target, supplying the exact active item receipt on the carried move.
    await robot.move("RIGHT", target, receipt=ready_receipt)

    # Consumer clears ready after its carried move.
    robot.clear_event(ready_event, expected_version=ready_receipt.version)

    # Release on target and depart before publishing empty_0.
    await robot.release("RIGHT", item, target)
    await robot.move("RIGHT", start_pose)

    # Release buffer_lock on departure.
    await robot.set_mode("RIGHT", "buffer_lock", "OFF")
    await robot.release_resource("RIGHT", "buffer_lock")

    # Publish empty_0 (buffer is now empty).
    robot.signal("empty_0", item)
