import asyncio

async def run_task(robot):
    """
    Executes the C3_EXCHANGE task with RQ2 resource constraints.
    Strategy: Serial execution.
    1. LEFT acquires and releases resources rq2_gap_0, rq2_gap_1, rq2_gap_2.
    2. LEFT signals rq2_gate.
    3. LEFT waits for rq2_gate.
    4. LEFT performs the dual-arm exchange:
       - Deposit LEFT part (left_part) to left_pad.
       - Deposit RIGHT part (right_part) to right_pad.
       - Wait for peer ready events (simulated via self-signaling in serial mode).
       - Pick up peer parts and move to targets.
       - Clear events and move to depart.
    5. LEFT clears rq2_gate.
    """

    # --- RQ2 Resource Lifecycle (LEFT) ---
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 in numeric order.
    # Mode must be OFF to release.
    for rid in ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]:
        await robot.acquire("LEFT", rid, timeout_s=4.0)
        await robot.set_mode("LEFT", rid, "OFF")
        await robot.release_resource("LEFT", rid)

    # --- RQ2 Gate Producer/Consumer (LEFT) ---
    # Signal rq2_gate exactly once.
    gate_receipt = robot.signal("rq2_gate")
    
    # Wait for rq2_gate immediately after signal.
    # Use the receipt version to ensure we wait for the specific event we just signaled.
    # Note: wait_event returns the active receipt. In serial execution, this is immediate.
    active_gate_receipt = await robot.wait_event("rq2_gate", timeout_s=4.0)

    # --- Inherited Dual-Arm Mission (Serial Execution) ---
    # The task requires serial scheduling for the mission.
    # We perform LEFT actions then RIGHT actions, or interleave strictly.
    # Given "A: deposit LEFT then RIGHT, then consume LEFT then RIGHT", we follow that sequence.

    # 1. Deposit LEFT part
    # Approach: left_home -> left_source
    await robot.move("LEFT", "left_source")
    # Grasp left_part
    await robot.grasp("LEFT", "left_part")
    # Move to left_pad
    await robot.move("LEFT", "left_pad")
    # Release left_part at left_pad
    await robot.release("LEFT", "left_part", "left_pad")
    # Immediate departure (clear pad)
    await robot.move("LEFT", "left_clear")
    # Signal left_ready
    left_ready_receipt = robot.signal("left_ready")

    # 2. Deposit RIGHT part
    # Approach: right_home -> right_source
    await robot.move("RIGHT", "right_source")
    # Grasp right_part
    await robot.grasp("RIGHT", "right_part")
    # Move to right_pad
    await robot.move("RIGHT", "right_pad")
    # Release right_part at right_pad
    await robot.release("RIGHT", "right_part", "right_pad")
    # Immediate departure (clear pad)
    await robot.move("RIGHT", "right_clear")
    # Signal right_ready
    right_ready_receipt = robot.signal("right_ready")

    # 3. Consume LEFT part (Pick up right_part from right_pad and move to left_target)
    # Wait for peer ready (right_ready)
    # In serial mode, we just signaled it, so we wait for that specific version.
    peer_right_ready = await robot.wait_event("right_ready", timeout_s=4.0)
    
    # Approach: left_pickup_wait -> right_pad
    await robot.move("LEFT", "left_pickup_wait")
    # Grasp right_part
    await robot.grasp("LEFT", "right_part")
    # Move to left_target carrying the peer receipt
    await robot.move("LEFT", "left_target", receipt=peer_right_ready)
    # Release right_part at left_target
    await robot.release("LEFT", "right_part", "left_target")
    # Clear right_ready event
    robot.clear_event("right_ready", expected_version=peer_right_ready.version)

    # 4. Consume RIGHT part (Pick up left_part from left_pad and move to right_target)
    # Wait for peer ready (left_ready)
    peer_left_ready = await robot.wait_event("left_ready", timeout_s=4.0)

    # Approach: right_pickup_wait -> left_pad
    await robot.move("RIGHT", "right_pickup_wait")
    # Grasp left_part
    await robot.grasp("RIGHT", "left_part")
    # Move to right_target carrying the peer receipt
    await robot.move("RIGHT", "right_target", receipt=peer_left_ready)
    # Release left_part at right_target
    await robot.release("RIGHT", "left_part", "right_target")
    # Clear left_ready event
    robot.clear_event("left_ready", expected_version=peer_left_ready.version)

    # --- Final Departure ---
    # Move arms to departure poses
    await robot.move("LEFT", "left_depart")
    await robot.move("RIGHT", "right_depart")

    # --- RQ2 Gate Cleanup ---
    # Clear rq2_gate after the mission is complete.
    robot.clear_event("rq2_gate", expected_version=active_gate_receipt.version)
