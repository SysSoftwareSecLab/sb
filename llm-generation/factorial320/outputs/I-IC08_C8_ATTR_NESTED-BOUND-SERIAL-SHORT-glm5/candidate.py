import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- RQ2 gate resource checks (serial, numeric order) ----
    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 5)
        await robot.release_resource("LEFT", gap)

    # ---- Signal rq2_gate exactly once, wait immediately ----
    gate_receipt = robot.signal("rq2_gate")
    gate_wait = await robot.wait_event("rq2_gate", 5)

    # ---- Inherited dual-arm buffer mission (SERIAL) ----
    # Episode 1: part_0 LEFT producer -> RIGHT consumer
    await _producer_episode(robot, "part_0", "source_0", "buffer_0",
                            "left_home", "left_wait", "ready_0")
    await _consumer_episode(robot, "part_0", "buffer_0", "target_0",
                            "right_home", "right_wait", "ready_0")

    # Producer waits and clears empty_0 before entering buffer with second part.
    empty_wait_0 = await robot.wait_event("empty_0", 5)
    robot.clear_event("empty_0", expected_version=empty_wait_0.version)

    # For item 1: inspect both readiness facts (serial checks inside loop branch).
    await robot.inspect("LEFT", "line_clear")
    await robot.inspect("LEFT", "receiver_ready")

    # Episode 2: part_1 LEFT producer -> RIGHT consumer
    await _producer_episode(robot, "part_1", "source_1", "buffer_1",
                            "left_home", "left_wait", "ready_1")
    await _consumer_episode(robot, "part_1", "buffer_1", "target_1",
                            "right_home", "right_wait", "ready_1")

    # ---- Clear rq2_gate after the protected mission ----
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
    return


async def _producer_episode(robot: Robot, item: str, source: str,
                            buffer: str, home: str, wait: str,
                            ready_event: str) -> None:
    # LEFT owns tool from before each source pickup through ready publication.
    await robot.acquire("LEFT", "tool", 5)

    # Approach source from left_home, then immediately grasp (no intervening calls).
    await robot.move("LEFT", source)
    grasp_obs = await robot.grasp("LEFT", item)

    # Depart source.
    await robot.move("LEFT", wait)

    # Enter buffer: own buffer_lock during buffer entry and departure.
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", buffer)

    # Release part at buffer, then immediately depart.
    await robot.release("LEFT", item, buffer)
    await robot.move("LEFT", home)

    # Release buffer_lock on exit.
    await robot.release_resource("LEFT", "buffer_lock")

    # Publish ready with the exact active grasp observation as item receipt.
    ready_receipt = robot.signal(ready_event, item)

    # Release tool on every exit.
    await robot.release_resource("LEFT", "tool")

    # Producer places each part at buffer and departs before ready publication:
    # ready was signaled above after departure. Keep receipt for consumer.
    _ = ready_receipt
    _ = grasp_obs


async def _consumer_episode(robot: Robot, item: str, buffer: str,
                            target: str, home: str, wait: str,
                            ready_event: str) -> None:
    # Consumer waits the corresponding ready receipt before pickup.
    ready_receipt = await robot.wait_event(ready_event, 10)

    # Enter buffer: own buffer_lock during buffer entry and departure.
    await robot.acquire("RIGHT", "buffer_lock", 5)

    # Approach buffer from right_home, then immediately grasp.
    await robot.move("RIGHT", buffer)
    grasp_obs = await robot.grasp("RIGHT", item, observation=ready_receipt)

    # Depart buffer.
    await robot.move("RIGHT", wait)

    # Release buffer_lock on exit.
    await robot.release_resource("RIGHT", "buffer_lock")

    # Supply the exact active item receipt on carried move to target.
    await robot.move("RIGHT", target, receipt=ready_receipt)

    # Consumer clears ready after its carried move.
    robot.clear_event(ready_event, expected_version=ready_receipt.version)

    # Release on target and depart before publishing empty_0.
    await robot.release("RIGHT", item, target)
    await robot.move("RIGHT", home)

    # Publish empty_0 (only after first consumer episode; second still signals).
    empty_receipt = robot.signal("empty_0", item)
    _ = empty_receipt
    _ = grasp_obs
