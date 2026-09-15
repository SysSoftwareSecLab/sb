import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot):
    # RQ2 gate protocol (serial): signal rq2_gate, acquire/release three gaps
    # in numeric order with LEFT, then wait the exact active rq2_gate receipt
    # and clear that version after the protected scope.
    gate_receipt = robot.signal("rq2_gate")

    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 5)
        await robot.release_resource("LEFT", gap)

    await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # Inherited dual-arm buffer mission (serial scheduling).
    # Episode 1: LEFT produces part_0 to buffer; RIGHT consumes to target_0.
    await robot.move("LEFT", "source_0")
    await robot.grasp("LEFT", "part_0")
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", "buffer_0", receipt=None)
    await robot.release("LEFT", "part_0", "buffer_0")
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")
    ready_0_receipt = robot.signal("ready_0", item_id="part_0")

    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", "buffer_0", receipt=ready_0_receipt)
    await robot.grasp("RIGHT", "part_0")
    await robot.move("RIGHT", "target_0", receipt=ready_0_receipt)
    robot.clear_event("ready_0", expected_version=ready_0_receipt.version)
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")
    empty_0_receipt = robot.signal("empty_0", item_id="part_0")

    # Episode 2: LEFT produces part_1 to buffer; RIGHT consumes to target_1.
    await robot.wait_event("empty_0", 5)
    robot.clear_event("empty_0", expected_version=empty_0_receipt.version)

    await robot.move("LEFT", "left_wait")
    await robot.move("LEFT", "source_1")
    await robot.grasp("LEFT", "part_1")
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", "buffer_1", receipt=None)
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")
    ready_1_receipt = robot.signal("ready_1", item_id="part_1")

    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", "right_wait")
    await robot.move("RIGHT", "buffer_1", receipt=ready_1_receipt)
    await robot.grasp("RIGHT", "part_1")
    await robot.move("RIGHT", "target_1", receipt=ready_1_receipt)
    robot.clear_event("ready_1", expected_version=ready_1_receipt.version)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")
