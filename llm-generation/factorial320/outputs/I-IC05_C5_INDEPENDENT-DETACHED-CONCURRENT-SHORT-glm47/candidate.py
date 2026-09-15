import asyncio

async def run_task(robot):
    """
    Executes the CONCURRENT dual-arm task with RQ2 gate protocol.
    Structure:
    1. Acquire and release resources rq2_gap_0, rq2_gap_1, rq2_gap_2 sequentially with LEFT.
    2. Signal rq2_gate.
    3. Wait for rq2_gate.
    4. Clear rq2_gate.
    5. Execute dual-arm mission concurrently:
       - LEFT: Move left_part from left_source to left_target, then depart.
       - RIGHT: Move right_part from right_source to right_target, then depart.
    """

    # --- Phase 1: Resource Lifecycle (LEFT only) ---
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # "Complete all three rq2_gap resource checks before signalling rq2_gate"
    
    gap_resources = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    for res_id in gap_resources:
        # Acquire
        await robot.acquire("LEFT", res_id, timeout_s=4.0)
        # Release
        await robot.release_resource("LEFT", res_id)

    # --- Phase 2: Event Protocol ---
    # "Signal rq2_gate exactly once"
    # "wait its exact active receipt exactly once"
    # "clear exactly that version after its assigned protected scope"
    
    # Signal the gate
    gate_receipt = robot.signal("rq2_gate")
    
    # Wait for the gate (Consumer)
    # "wait immediately after the signal"
    # Note: The signal makes the event active. wait_event returns the active receipt.
    # We must wait for the event we just signaled.
    await robot.wait_event("rq2_gate", timeout_s=4.0)
    
    # Clear the gate
    # "clear exactly that version"
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- Phase 3: Concurrent Dual-Arm Mission ---
    # "Use joined concurrent scheduling for both the inherited dual-arm mission"
    # "Complete and clear the rq2_gate protocol before starting the complete inherited dual-arm mission"
    
    async def left_arm_mission():
        # Approach: left_home -> left_source
        await robot.move("LEFT", "left_source")
        # Grasp left_part
        await robot.grasp("LEFT", "left_part")
        # Transport: left_source -> left_target
        await robot.move("LEFT", "left_target")
        # Release left_part at left_target
        await robot.release("LEFT", "left_part", "left_target")
        # Depart: left_target -> left_depart
        await robot.move("LEFT", "left_depart")

    async def right_arm_mission():
        # Approach: right_home -> right_source
        await robot.move("RIGHT", "right_source")
        # Grasp right_part
        await robot.grasp("RIGHT", "right_part")
        # Transport: right_source -> right_target
        await robot.move("RIGHT", "right_target")
        # Release right_part at right_target
        await robot.release("RIGHT", "right_part", "right_target")
        # Depart: right_target -> right_depart
        await robot.move("RIGHT", "right_depart")

    # Run both arms concurrently
    await asyncio.gather(left_arm_mission(), right_arm_mission())
