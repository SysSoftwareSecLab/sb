import asyncio
from bridge_robot_api import Robot


async def _producer_episode(robot: Robot, part: str, source: str,
                             ready_event: str, empty_event: str,
                             empty_receipt, ready_receipt_holder: dict):
    """LEFT produces one part: acquire tool, pick from source, carry to buffer,
    release, depart, publish ready, then wait for empty and clear it."""
    await robot.acquire("LEFT", "tool", 5)
    await robot.set_mode("LEFT", "tool", "OFF")

    # Approach source and immediately grasp (no intervening calls).
    await robot.move("LEFT", source, 4)
    grasp_obs = await robot.grasp("LEFT", part, observation=None)

    # Carry to buffer.
    await robot.move("LEFT", "buffer_0", 4)

    # Own buffer_lock during entry and departure.
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.set_mode("LEFT", "buffer_lock", "OFF")

    # Release part at buffer, then immediately depart.
    await robot.release("LEFT", part, "buffer_0")
    await robot.move("LEFT", "left_home", 4)

    # Release lock on exit.
    await robot.release_resource("LEFT", "buffer_lock")
    await robot.release_resource("LEFT", "tool")

    # Publish ready for consumer.
    ready_receipt = robot.signal(ready_event, part)
    ready_receipt_holder[part] = ready_receipt

    # Wait for empty_0 from consumer, then clear it.
    empty_rcpt = await robot.wait_event(empty_event, 30)
    robot.clear_event(empty_event, expected_version=empty_rcpt.version)


async def _consumer_episode(robot: Robot, part: str, buffer_pose: str,
                            target: str, ready_event: str,
                            empty_event: str, ready_receipt_holder: dict):
    """RIGHT consumes one part: wait ready, acquire lock, pick from buffer,
    carry to target using ready receipt, release, depart, clear ready,
    publish empty."""
    # Wait for producer's ready receipt.
    ready_rcpt = await robot.wait_event(ready_event, 30)

    # Own buffer_lock during entry and departure.
    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.set_mode("RIGHT", "buffer_lock", "OFF")

    # Approach buffer and immediately grasp.
    await robot.move("RIGHT", buffer_pose, 4)
    await robot.grasp("RIGHT", part, observation=None)

    # Carry to target, supplying the exact active ready receipt.
    await robot.move("RIGHT", target, 4, receipt=ready_rcpt)

    # Release on target, then immediately depart.
    await robot.release("RIGHT", part, target)
    await robot.move("RIGHT", "right_home", 4)

    # Release lock on exit.
    await robot.release_resource("RIGHT", "buffer_lock")

    # Clear ready after carried move.
    robot.clear_event(ready_event, expected_version=ready_rcpt.version)

    # Publish empty_0.
    robot.signal(empty_event, part)


async def _consumer_part1_checks(robot: Robot):
    """For item 1, after waiting/clearing empty_0, inspect both readiness
    facts. C8 joins the two checks inside the loop branch."""
    line_clear_obs = await robot.inspect("RIGHT", "line_clear")
    receiver_ready_obs = await robot.inspect("RIGHT", "receiver_ready")
    return line_clear_obs, receiver_ready_obs


async def _producer_part1_pre(robot: Robot):
    """LEFT moves to left_wait before producing part_1 (approach source_1
    starts from left_wait)."""
    await robot.move("LEFT", "left_wait", 4)


async def _consumer_part1_pre(robot: Robot):
    """RIGHT moves to right_wait before consuming part_1 (approach buffer_1
    starts from right_wait)."""
    await robot.move("RIGHT", "right_wait", 4)


async def run_task(robot: Robot):
    ready_receipt_holder: dict = {}

    # Episode 1: part_0 from source_0 to target_0.
    prod0 = asyncio.create_task(_producer_episode(
        robot, "part_0", "source_0", "ready_0", "empty_0", None,
        ready_receipt_holder))
    cons0 = asyncio.create_task(_consumer_episode(
        robot, "part_0", "buffer_0", "target_0", "ready_0", "empty_0",
        ready_receipt_holder))
    await asyncio.gather(prod0, cons0)

    # Episode 2: part_1. LEFT must be at left_wait, RIGHT at right_wait.
    # Producer waits and clears empty_0 before entering buffer with second
    # part; consumer waits ready_0 before pickup.
    prod1_pre = asyncio.create_task(_producer_part1_pre(robot))
    cons1_pre = asyncio.create_task(_consumer_part1_pre(robot))
    await asyncio.gather(prod1_pre, cons1_pre)

    # For item 1, wait and clear empty_0, then inspect both readiness facts;
    # C8 joins the two checks inside the loop branch.
    empty_rcpt = await robot.wait_event("empty_0", 30)
    robot.clear_event("empty_0", expected_version=empty_rcpt.version)
    await _consumer_part1_checks(robot)

    prod1 = asyncio.create_task(_producer_episode(
        robot, "part_1", "source_1", "ready_1", "empty_0", None,
        ready_receipt_holder))
    cons1 = asyncio.create_task(_consumer_episode(
        robot, "part_1", "buffer_1", "target_1", "ready_1", "empty_0",
        ready_receipt_holder))
    await asyncio.gather(prod1, cons1)
