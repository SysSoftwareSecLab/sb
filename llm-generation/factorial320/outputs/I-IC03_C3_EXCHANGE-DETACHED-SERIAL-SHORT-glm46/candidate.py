import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # --- RQ2_GATE PROTOCOL (LEFT ARM) ---
    # Acquire resources in numeric order
    await robot.acquire("LEFT", "rq2_gap_0", 4.0)
    await robot.acquire("LEFT", "rq2_gap_1", 4.0)
    await robot.acquire("LEFT", "rq2_gap_2", 4.0)

    # Signal the gate
    gate_receipt = robot.signal("rq2_gate")

    # Wait for the gate immediately after signal
    # Note: The task requires serial scheduling, so we await this before proceeding.
    # The receipt returned by wait_event must be the one used for the move.
    active_gate_receipt = await robot.wait_event("rq2_gate", 4.0)

    # Perform the protected move using the active receipt
    # We move to a neutral pose to satisfy the "carried move" requirement within the scope.
    # Using left_clear as a safe intermediate.
    await robot.move("LEFT", "left_clear", timeout_s=4.0, receipt=active_gate_receipt)

    # Clear the event after the move
    robot.clear_event("rq2_gate", expected_version=active_gate_receipt.version)

    # Release resources
    await robot.release_resource("LEFT", "rq2_gap_0")
    await robot.release_resource("LEFT", "rq2_gap_1")
    await robot.release_resource("LEFT", "rq2_gap_2")

    # --- DUAL-ARM EXCHANGE MISSION ---
    # Strategy: Serial execution.
    # 1. LEFT deposits its part (left_part) on left_pad.
    # 2. RIGHT deposits its part (right_part) on right_pad.
    # 3. LEFT waits for right_ready, then picks up right_part from right_pad.
    # 4. RIGHT waits for left_ready, then picks up left_part from left_pad.
    # 5. LEFT moves right_part to right_target.
    # 6. RIGHT moves left_part to left_target.
    # 7. Both arms move to departure.

    # LEFT: Deposit left_part
    # Approach from left_home to left_source
    await robot.move("LEFT", "left_source", timeout_s=4.0)
    # Grasp left_part
    await robot.grasp("LEFT", "left_part")
    # Move to left_pad
    await robot.move("LEFT", "left_pad", timeout_s=4.0)
    # Release left_part
    await robot.release("LEFT", "left_part", "left_pad")
    # Immediate departure (clear the pad)
    await robot.move("LEFT", "left_pickup_wait", timeout_s=4.0)
    # Signal left_ready
    robot.signal("left_ready")

    # RIGHT: Deposit right_part
    # Approach from right_home to right_source
    await robot.move("RIGHT", "right_source", timeout_s=4.0)
    # Grasp right_part
    await robot.grasp("RIGHT", "right_part")
    # Move to right_pad
    await robot.move("RIGHT", "right_pad", timeout_s=4.0)
    # Release right_part
    await robot.release("RIGHT", "right_part", "right_pad")
    # Immediate departure (clear the pad)
    await robot.move("RIGHT", "right_pickup_wait", timeout_s=4.0)
    # Signal right_ready
    robot.signal("right_ready")

    # LEFT: Consume right_part
    # Wait for peer ready
    right_ready_receipt = await robot.wait_event("right_ready", 4.0)
    # Approach from left_pickup_wait to right_pad
    await robot.move("LEFT", "right_pad", timeout_s=4.0)
    # Grasp right_part
    await robot.grasp("LEFT", "right_part")
    # Move to right_target carrying the receipt
    await robot.move("LEFT", "right_target", timeout_s=4.0, receipt=right_ready_receipt)
    # Release right_part
    await robot.release("LEFT", "right_part", "right_target")
    # Clear the event after the move
    robot.clear_event("right_ready", expected_version=right_ready_receipt.version)
    # Depart
    await robot.move("LEFT", "left_depart", timeout_s=4.0)

    # RIGHT: Consume left_part
    # Wait for peer ready
    left_ready_receipt = await robot.wait_event("left_ready", 4.0)
    # Approach from right_pickup_wait to left_pad
    await robot.move("RIGHT", "left_pad", timeout_s=4.0)
    # Grasp left_part
    await robot.grasp("RIGHT", "left_part")
    # Move to left_target carrying the receipt
    await robot.move("RIGHT", "left_target", timeout_s=4.0, receipt=left_ready_receipt)
    # Release left_part
    await robot.release("RIGHT", "left_part", "left_target")
    # Clear the event after the move
    robot.clear_event("left_ready", expected_version=left_ready_receipt.version)
    # Depart
    await robot.move("RIGHT", "right_depart", timeout_s=4.0)
