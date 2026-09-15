import asyncio
from bridge_robot_api import Robot


async def _move(robot, arm, pose, timeout_s=None, receipt=None):
    return await robot.move(arm, pose, timeout_s=timeout_s, receipt=receipt)


async def _producer_episode_part0(robot, tool_acq, empty_evt):
    """LEFT producer: pick part_0 at source_0, place at buffer_0, depart, publish ready_0."""
    # Own tool from before source pickup through ready publication.
    await robot.acquire("LEFT", "tool", 10)

    # Approach source_0 from left_home, then immediately grasp part_0.
    await _move(robot, "LEFT", "source_0")
    obs0 = await robot.grasp("LEFT", "part_0")

    # Carry to buffer_0.
    await _move(robot, "LEFT", "buffer_0")

    # Release part_0 at buffer_0, then immediately depart.
    await robot.release("LEFT", "part_0", "buffer_0")
    await _move(robot, "LEFT", "left_home")

    # Publish ready_0 (producer departs before ready publication).
    rdy0 = robot.signal("ready_0", "part_0")

    # Release tool on every exit.
    await robot.set_mode("LEFT", "tool", "OFF")
    await robot.release_resource("LEFT", "tool")

    return rdy0


async def _consumer_episode_part0(robot, ready_receipt):
    """RIGHT consumer: wait ready_0, pick part_0 at buffer_0, carry to target_0, depart, publish empty_0."""
    # Wait for ready_0 (already signaled; wait returns active receipt).
    rdy0 = await robot.wait_event("ready_0", 10)

    # Approach buffer_0 from right_home, then immediately grasp part_0.
    await _move(robot, "RIGHT", "buffer_0")
    await robot.grasp("RIGHT", "part_0")

    # Carry to target_0, supplying the exact active item receipt on carried move.
    await _move(robot, "RIGHT", "target_0", receipt=rdy0)

    # Clear ready after carried move completes.
    robot.clear_event("ready_0", expected_version=rdy0.version)

    # Release on target and depart before publishing empty_0.
    await robot.release("RIGHT", "part_0", "target_0")
    await _move(robot, "RIGHT", "right_home")

    # Publish empty_0.
    emp0 = robot.signal("empty_0", "part_0")
    return emp0


async def _producer_episode_part1(robot, empty_receipt):
    """LEFT producer: wait empty_0, clear it, inspect readiness facts, pick part_1, place at buffer_1, depart, publish ready_1."""
    # Wait and clear empty_0 before entering buffer with second part.
    emp0 = await robot.wait_event("empty_0", 10)
    robot.clear_event("empty_0", expected_version=emp0.version)

    # Inspect both readiness facts serially (C7 checks serially).
    await robot.inspect("LEFT", "line_clear")
    await robot.inspect("LEFT", "receiver_ready")

    # Own tool from before source pickup through ready publication.
    await robot.acquire("LEFT", "tool", 10)

    # Move to left_wait (start_pose for source_1 approach).
    await _move(robot, "LEFT", "left_wait")

    # Approach source_1 from left_wait, then immediately grasp part_1.
    await _move(robot, "LEFT", "source_1")
    await robot.grasp("LEFT", "part_1")

    # Carry to buffer_1.
    await _move(robot, "LEFT", "buffer_1")

    # Release part_1 at buffer_1, then immediately depart.
    await robot.release("LEFT", "part_1", "buffer_1")
    await _move(robot, "LEFT", "left_home")

    # Publish ready_1.
    rdy1 = robot.signal("ready_1", "part_1")

    # Release tool on every exit.
    await robot.set_mode("LEFT", "tool", "OFF")
    await robot.release_resource("LEFT", "tool")

    return rdy1


async def _consumer_episode_part1(robot, ready_receipt):
    """RIGHT consumer: wait ready_1, pick part_1 at buffer_1, carry to target_1, depart, publish empty_0."""
    rdy1 = await robot.wait_event("ready_1", 10)

    # Move to right_wait (start_pose for buffer_1 approach).
    await _move(robot, "RIGHT", "right_wait")

    # Approach buffer_1 from right_wait, then immediately grasp part_1.
    await _move(robot, "RIGHT", "buffer_1")
    await robot.grasp("RIGHT", "part_1")

    # Carry to target_1, supplying exact active item receipt.
    await _move(robot, "RIGHT", "target_1", receipt=rdy1)

    # Clear ready after carried move.
    robot.clear_event("ready_1", expected_version=rdy1.version)

    # Release on target and depart before publishing empty_0.
    await robot.release("RIGHT", "part_1", "target_1")
    await _move(robot, "RIGHT", "right_home")

    # Publish empty_0.
    emp0 = robot.signal("empty_0", "part_1")
    return emp0


async def run_task(robot: Robot):
    """C7_ATTR_FLAT-SERIAL-LH: A alternates complete producer/consumer episodes.

    Episode 1: LEFT produces part_0 to buffer; RIGHT consumes part_0 to target_0.
    Episode 2: LEFT produces part_1 to buffer; RIGHT consumes part_1 to target_1.
    """
    # Episode 1 - part_0
    rdy0 = await _producer_episode_part0(robot, None, None)
    emp0 = await _consumer_episode_part0(robot, rdy0)

    # Episode 2 - part_1 (producer waits/clears empty_0, inspects readiness facts)
    rdy1 = await _producer_episode_part1(robot, emp0)
    await _consumer_episode_part1(robot, rdy1)
