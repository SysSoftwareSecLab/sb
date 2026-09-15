import asyncio
from bridge_robot_api import Robot  # noqa: F401  (type hint only)


async def run_task(robot):
    """IC08_C8_ATTR_NESTED-DETACHED-SERIAL-SHORT.

    Structure:
      1. rq2_gate protocol (serial): acquire rq2_gap_0/1/2 with LEFT in order,
         signal rq2_gate once, wait its active receipt once, clear that version.
      2. Inherited dual-arm buffer mission (serial scheduling):
         A alternates complete producer/consumer episodes for part_0 and part_1.
    """

    # ---- Phase 1: rq2_gate protocol ----
    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 5)
        await robot.release_resource("LEFT", gap)

    gate_receipt = robot.signal("rq2_gate")
    waited = await robot.wait_event("rq2_gate", 5)
    assert waited.version == gate_receipt.version
    robot.clear_event("rq2_gate", expected_version=waited.version)

    # ---- Phase 2: inherited dual-arm buffer mission (serial) ----

    # Episode 1: part_0  (LEFT produces, RIGHT consumes)
    await _produce_episode(robot, "part_0", "source_0", "buffer_0",
                           "left_home", "left_wait", "ready_0")
    await _consume_episode(robot, "part_0", "buffer_0", "target_0",
                           "right_home", "right_wait", "ready_0")

    # Episode 2: part_1  (LEFT produces, RIGHT consumes)
    await _produce_episode(robot, "part_1", "source_1", "buffer_1",
                           "left_wait", "left_home", "ready_1")
    await _consume_episode(robot, "part_1", "buffer_1", "target_1",
                           "right_wait", "right_home", "ready_1")


async def _produce_episode(robot, item, source, buffer_pose,
                           start_pose, next_left_pose, ready_event):
    """LEFT picks item from source, places at buffer, departs, publishes ready.

    Owns tool from before source pickup through ready publication and releases
    it on every exit.  Waits/clears empty_0 before entering buffer with part_1.
    """
    is_second = (item == "part_1")

    # Acquire tool before source pickup.
    await robot.acquire("LEFT", "tool", 5)

    # Approach source from declared start_pose, then immediately grasp.
    await robot.move("LEFT", start_pose)
    await robot.move("LEFT", source)
    await robot.grasp("LEFT", item)

    # Move toward buffer; for part_1, wait/clear empty_0 before buffer entry.
    if is_second:
        empty_receipt = await robot.wait_event("empty_0", 30)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

    # Enter buffer (own buffer_lock during entry and departure).
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", buffer_pose)
    await robot.release("LEFT", item, buffer_pose)

    # Immediate separating departure from buffer.
    await robot.move("LEFT", next_left_pose)
    await robot.release_resource("LEFT", "buffer_lock")

    # Release tool on exit (before ready publication).
    await robot.release_resource("LEFT", "tool")

    # Publish ready after departure.
    robot.signal(ready_event, item)


async def _consume_episode(robot, item, buffer_pose, target_pose,
                           start_pose, next_right_pose, ready_event):
    """RIGHT waits ready receipt, picks from buffer, carries to target using
    that exact active item receipt, releases on target, departs, publishes
    empty_0, then clears ready after the carried move.
    """
    ready_receipt = await robot.wait_event(ready_event, 30)

    # Approach buffer from declared start_pose, then immediately grasp.
    await robot.move("RIGHT", start_pose)
    await robot.move("RIGHT", buffer_pose)
    await robot.grasp("RIGHT", item)

    # Carried move to target supplies the exact active item receipt.
    await robot.move("RIGHT", target_pose, receipt=ready_receipt)

    # Clear ready after the carried move.
    robot.clear_event(ready_event, expected_version=ready_receipt.version)

    # Release on target, then immediate separating departure.
    await robot.release("RIGHT", item, target_pose)
    await robot.move("RIGHT", next_right_pose)

    # Publish empty_0 after departure.
    robot.signal("empty_0", item)
