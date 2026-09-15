import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- RQ2 gap resource checks (LEFT, numeric order) ----
    await robot.acquire("LEFT", "rq2_gap_0", 5)
    await robot.release_resource("LEFT", "rq2_gap_0")

    await robot.acquire("LEFT", "rq2_gap_1", 5)
    await robot.release_resource("LEFT", "rq2_gap_1")

    await robot.acquire("LEFT", "rq2_gap_2", 5)
    await robot.release_resource("LEFT", "rq2_gap_2")

    # ---- Signal rq2_gate exactly once, wait immediately ----
    gate_receipt = robot.signal("rq2_gate")
    gate_wait_receipt = await robot.wait_event("rq2_gate", 5)

    # ---- Inherited dual-arm buffer mission (serial) ----
    # Episode 1: part_0 LEFT producer -> RIGHT consumer
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", "source_0", 5)
    await robot.grasp("LEFT", "part_0")
    await robot.move("LEFT", "buffer_0", 5, receipt=gate_receipt)
    await robot.release("LEFT", "part_0", "buffer_0")
    await robot.move("LEFT", "left_home", 5)
    await robot.release_resource("LEFT", "buffer_lock")

    ready_0_receipt = robot.signal("ready_0")

    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", "buffer_0", 5)
    await robot.grasp("RIGHT", "part_0", observation=ready_0_receipt)
    await robot.move("RIGHT", "target_0", 5, receipt=ready_0_receipt)
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_home", 5)
    await robot.release_resource("RIGHT", "buffer_lock")

    clear_event_after_move("ready_0", ready_0_receipt, robot)

    empty_0_receipt = robot.signal("empty_0")

    # Episode 2: part_1 LEFT producer -> RIGHT consumer
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", "left_wait", 5)
    await robot.move("LEFT", "source_1", 5)
    await robot.grasp("LEFT", "part_1")
    await robot.move("LEFT", "buffer_1", 5, receipt=gate_receipt)
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_home", 5)
    await robot.release_resource("LEFT", "buffer_lock")

    ready_1_receipt = robot.signal("ready_1")

    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", "right_wait", 5)
    await robot.move("RIGHT", "buffer_1", 5)
    await robot.grasp("RIGHT", "part_1", observation=ready_1_receipt)
    await robot.move("RIGHT", "target_1", 5, receipt=ready_1_receipt)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home", 5)
    await robot.release_resource("RIGHT", "buffer_lock")

    clear_event_after_move("ready_1", ready_1_receipt, robot)

    # Producer waits and clears empty_0 before entering buffer with second part:
    # the second producer episode above was preceded by waiting empty_0.
    await robot.wait_event("empty_0", 5)
    robot.clear_event("empty_0", expected_version=empty_0_receipt.version)

    # ---- Clear rq2_gate after the complete inherited mission ----
    robot.clear_event("rq2_gate", expected_version=gate_wait_receipt.version)


def clear_event_after_move(event_id, receipt, robot):
    robot.clear_event(event_id, expected_version=receipt.version)
