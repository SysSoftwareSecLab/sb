import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- Phase 1: rq2_gate protocol (serial) ----
    gate_receipt = robot.signal("rq2_gate")

    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 5)
        await robot.release_resource("LEFT", gap)

    await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # ---- Phase 2: inherited dual-arm buffer mission (serial) ----
    # Episode for part_0
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", "source_0")
    await robot.grasp("LEFT", "part_0")
    await robot.move("LEFT", "buffer_0")
    await robot.release("LEFT", "part_0", "buffer_0")
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")

    ready_receipt_0 = robot.signal("ready_0", "part_0")

    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", "buffer_0")
    await robot.grasp("RIGHT", "part_0", observation=ready_receipt_0)
    await robot.move("RIGHT", "target_0", receipt=ready_receipt_0)
    robot.clear_event("ready_0", expected_version=ready_receipt_0.version)
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")

    empty_receipt_0 = robot.signal("empty_0", "part_0")

    # Episode for part_1
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.wait_event("empty_0", 5)
    robot.clear_event("empty_0", expected_version=empty_receipt_0.version)
    await robot.move("LEFT", "source_1")
    await robot.grasp("LEFT", "part_1")
    await robot.move("LEFT", "buffer_1")
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")

    ready_receipt_1 = robot.signal("ready_1", "part_1")

    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", "buffer_1")
    await robot.grasp("RIGHT", "part_1", observation=ready_receipt_1)
    await robot.move("RIGHT", "target_1", receipt=ready_receipt_1)
    robot.clear_event("ready_1", expected_version=ready_receipt_1.version)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")
