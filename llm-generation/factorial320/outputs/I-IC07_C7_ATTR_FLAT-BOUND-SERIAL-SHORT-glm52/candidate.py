import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- RQ2 gap resource checks (serial, numeric order, LEFT only) ----
    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 5)
        await robot.release_resource("LEFT", gap)

    # ---- rq2_gate lifecycle: signal, wait exact receipt, keep active ----
    gate_receipt = robot.signal("rq2_gate")
    waited_gate = await robot.wait_event("rq2_gate", 5)
    assert waited_gate.version == gate_receipt.version

    # ---- Inherited dual-arm buffer mission (serial scheduling) ----
    await _episode(robot, part="part_0", source="source_0", buffer="buffer_0",
                   target="target_0", ready="ready_0")
    await _episode(robot, part="part_1", source="source_1", buffer="buffer_1",
                   target="target_1", ready="ready_1")

    # ---- Clear rq2_gate after the protected scope ----
    robot.clear_event("rq2_gate", expected_version=waited_gate.version)


async def _episode(robot: Robot, *, part: str, source: str, buffer: str,
                   target: str, ready: str) -> None:
    # Producer (LEFT): own tool through source pickup until ready publication.
    await robot.acquire("LEFT", "tool", 5)
    await robot.move("LEFT", source)
    await robot.grasp("LEFT", part)
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", buffer)
    await robot.release("LEFT", part, buffer)
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")
    ready_receipt = robot.signal(ready)
    await robot.release_resource("LEFT", "tool")

    # Consumer (RIGHT): wait ready, carry to target using that exact receipt.
    waited_ready = await robot.wait_event(ready, 5)
    assert waited_ready.version == ready_receipt.version
    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", buffer)
    await robot.grasp("RIGHT", part)
    await robot.move("RIGHT", target, receipt=waited_ready)
    robot.clear_event(ready, expected_version=waited_ready.version)
    await robot.release("RIGHT", part, target)
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")

    # Producer (LEFT): wait and clear empty_0 before entering buffer again.
    empty_receipt = await robot.wait_event("empty_0", 5)
    robot.clear_event("empty_0", expected_version=empty_receipt.version)
