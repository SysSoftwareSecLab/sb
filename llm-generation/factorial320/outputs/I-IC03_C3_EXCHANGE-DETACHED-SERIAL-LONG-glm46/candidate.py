import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- RQ2_GATE PROTOCOL ---
    # 1. Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # 2. Acquire and release resources rq2_gap_0, rq2_gap_1, rq2_gap_2 with LEFT arm, in numeric order
    #    Must be OFF mode (initial mode is OFF).
    for res_id in ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]:
        await robot.acquire("LEFT", res_id, timeout_s=4.0)
        await robot.release_resource("LEFT", res_id)
    
    # 3. Wait for rq2_gate (exact active receipt)
    #    Wait must happen after resource checks.
    await robot.wait_event("rq2_gate", timeout_s=4.0)
    
    # 4. Clear rq2_gate
    #    Clear must happen after wait.
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- DUAL-ARM EXCHANGE MISSION ---
    # Variant A: Deposit LEFT then RIGHT, then Consume LEFT then RIGHT.
    # Serial scheduling: execute sequentially.

    # --- PHASE 1: DEPOSIT ---
    
    # LEFT deposits its own part (left_part) on left_pad
    # Approach: left_home -> left_source
    await robot.move("LEFT", "left_source")
    # Grasp left_part
    await robot.grasp("LEFT", "left_part")
    # Move to left_pad
    await robot.move("LEFT", "left_pad")
    # Release left_part on left_pad
    await robot.release("LEFT", "left_part", "left_pad")
    # Immediate departure (clear pad)
    await robot.move("LEFT", "left_clear")
    # Publish ready event
    robot.signal("left_ready")

    # RIGHT deposits its own part (right_part) on right_pad
    # Approach: right_home -> right_source
    await robot.move("RIGHT", "right_source")
    # Grasp right_part
    await robot.grasp("RIGHT", "right_part")
    # Move to right_pad
    await robot.move("RIGHT", "right_pad")
    # Release right_part on right_pad
    await robot.release("RIGHT", "right_part", "right_pad")
    # Immediate departure (clear pad)
    await robot.move("RIGHT", "right_clear")
    # Publish ready event
    robot.signal("right_ready")

    # --- PHASE 2: CONSUME ---
    
    # LEFT consumes peer item (right_part) from right_pad to left_target
    # Condition: own deposit/clear done, wait for peer ready.
    peer_ready_left = await robot.wait_event("right_ready", timeout_s=4.0)
    
    # Approach: left_pickup_wait -> right_pad
    await robot.move("LEFT", "left_pickup_wait")
    # Grasp right_part
    await robot.grasp("LEFT", "right_part")
    # Move to left_target carrying the peer receipt
    await robot.move("LEFT", "left_target", receipt=peer_ready_left)
    # Release right_part
    await robot.release("LEFT", "right_part", "left_target")
    # Clear peer event after move
    robot.clear_event("right_ready", expected_version=peer_ready_left.version)
    # Depart to final goal
    await robot.move("LEFT", "left_depart")

    # RIGHT consumes peer item (left_part) from left_pad to right_target
    # Condition: own deposit/clear done, wait for peer ready.
    peer_ready_right = await robot.wait_event("left_ready", timeout_s=4.0)
    
    # Approach: right_pickup_wait -> left_pad
    await robot.move("RIGHT", "right_pickup_wait")
    # Grasp left_part
    await robot.grasp("RIGHT", "left_part")
    # Move to right_target carrying the peer receipt
    await robot.move("RIGHT", "right_target", receipt=peer_ready_right)
    # Release left_part
    await robot.release("RIGHT", "left_part", "right_target")
    # Clear peer event after move
    robot.clear_event("left_ready", expected_version=peer_ready_right.version)
    # Depart to final goal
    await robot.move("RIGHT", "right_depart")
