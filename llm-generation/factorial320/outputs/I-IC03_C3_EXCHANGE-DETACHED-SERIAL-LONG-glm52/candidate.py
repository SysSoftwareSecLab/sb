import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Phase 1: rq2_gate protocol (serial producer/consumer).
    gate_receipt = robot.signal("rq2_gate")
    await robot.acquire("LEFT", "rq2_gap_0", 5)
    await robot.release_resource("LEFT", "rq2_gap_0")
    await robot.acquire("LEFT", "rq2_gap_1", 5)
    await robot.release_resource("LEFT", "rq2_gap_1")
    await robot.acquire("LEFT", "rq2_gap_2", 5)
    await robot.release_resource("LEFT", "rq2_gap_2")
    waited_gate = await robot.wait_event("rq2_gate", 5)
    await robot.move("LEFT", "left_home")
    robot.clear_event("rq2_gate", expected_version=waited_gate.version)

    # Phase 2: inherited dual-arm exchange, serial schedule A:
    # deposit LEFT then RIGHT, then consume LEFT then RIGHT.

    # LEFT deposits left_part on left_pad.
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_pad")
    await robot.release("LEFT", "left_part", "left_pad")
    await robot.move("LEFT", "left_pickup_wait")
    left_ready = robot.signal("left_ready")

    # RIGHT deposits right_part on right_pad.
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_pad")
    await robot.release("RIGHT", "right_part", "right_pad")
    await robot.move("RIGHT", "right_pickup_wait")
    right_ready = robot.signal("right_ready")

    # LEFT consumes right_part: wait for peer ready, carry exact active receipt, clear after move.
    waited_right = await robot.wait_event("right_ready", 5)
    await robot.move("LEFT", "right_pad", receipt=waited_right)
    await robot.grasp("LEFT", "right_part")
    await robot.move("LEFT", "right_target")
    await robot.release("LEFT", "right_part", "right_target")
    await robot.move("LEFT", "left_depart")
    robot.clear_event("right_ready", expected_version=waited_right.version)

    # RIGHT consumes left_part.
    waited_left = await robot.wait_event("left_ready", 5)
    await robot.move("RIGHT", "left_pad", receipt=waited_left)
    await robot.grasp("RIGHT", "left_part")
    await robot.move("RIGHT", "left_target")
    await robot.release("RIGHT", "left_part", "left_target")
    await robot.move("RIGHT", "right_depart")
    robot.clear_event("left_ready", expected_version=waited_left.version)

    # Terminal state: both ready events inactive; rq2_gate already cleared.
    # rq2_gap_0/1/2 all free and OFF (released without set_mode).
    return
