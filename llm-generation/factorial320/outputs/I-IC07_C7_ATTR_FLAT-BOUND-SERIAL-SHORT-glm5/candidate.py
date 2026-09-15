import asyncio
from bridge_robot_api import MotionFault

async def run_task(robot):
    # ---- RQ2 gap resource checks (serial, LEFT, numeric order) ----
    for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", rid, 5)
        await robot.release_resource("LEFT", rid)

    # ---- rq2_gate: signal once, wait once, keep active during mission ----
    gate_receipt = robot.signal("rq2_gate")
    gate_wait = await robot.wait_event("rq2_gate", 5)

    # ---- Inherited dual-arm buffer mission (serial scheduling) ----
    await producer_episode(robot, "part_0", "source_0", "buffer_0", "ready_0", "left_home")
    await consumer_episode(robot, "part_0", "buffer_0", "target_0", "ready_0", "empty_0", "right_home")

    # Producer waits and clears empty_0 before entering buffer with second part.
    await robot.wait_event("empty_0", 5)
    robot.clear_event("empty_0", expected_version=1)

    await producer_episode(robot, "part_1", "source_1", "buffer_1", "ready_1", "left_wait")
    await consumer_episode(robot, "part_1", "buffer_1", "target_1", "ready_1", "empty_0", "right_wait")

    # ---- Clear rq2_gate only after the mission ----
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)


async def producer_episode(robot, part, source, buffer, ready_event, start_pose):
    # LEFT owns tool from before each source pickup through ready publication.
    await robot.acquire("LEFT", "tool", 5)

    # Approach source from start_pose, immediately grasp (no intervening calls).
    await robot.move("LEFT", start_pose, 5)
    await robot.move("LEFT", source, 5)
    grasp_obs = await robot.grasp("LEFT", part)

    # Acquire buffer_lock for buffer entry.
    await robot.acquire("LEFT", "buffer_lock", 5)

    # Move carried object to buffer and release on buffer support zone.
    await robot.move("LEFT", buffer, 5, receipt=grasp_obs)
    await robot.release("LEFT", part, buffer)

    # Immediate departure from buffer.
    await robot.move("LEFT", start_pose, 5)

    # Release buffer_lock on every exit.
    await robot.release_resource("LEFT", "buffer_lock")

    # Release tool on every exit.
    await robot.release_resource("LEFT", "tool")

    # Publish ready after departing buffer.
    robot.signal(ready_event, item_id=part)


async def consumer_episode(robot, part, buffer, target, ready_event, empty_event, start_pose):
    # Wait the corresponding ready receipt before pickup.
    ready_receipt = await robot.wait_event(ready_event, 10)

    # RIGHT owns buffer_lock during buffer entry and departure.
    await robot.acquire("RIGHT", "buffer_lock", 5)

    # Approach buffer from start_pose, immediately grasp.
    await robot.move("RIGHT", start_pose, 5)
    await robot.move("RIGHT", buffer, 5)
    grasp_obs = await robot.grasp("RIGHT", part)

    # Move carried object to target supplying the exact active item receipt.
    await robot.move("RIGHT", target, 5, receipt=ready_receipt)

    # Clear ready after the carried move.
    robot.clear_event(ready_event, expected_version=ready_receipt.version)

    # Release on target and depart before publishing empty.
    await robot.release("RIGHT", part, target)
    await robot.move("RIGHT", start_pose, 5)

    # Release buffer_lock on departure.
    await robot.release_resource("RIGHT", "buffer_lock")

    # Publish empty after departing target.
    robot.signal(empty_event, item_id=part)
