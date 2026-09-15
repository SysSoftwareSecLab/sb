import asyncio

async def run_task(robot):
    """
    Executes the C3_EXCHANGE-SERIAL-LH task.
    Strategy: Serial execution (LEFT then RIGHT) as per Variant A requirements.
    Sequence:
    1. LEFT deposits left_part at left_pad, clears event, departs.
    2. RIGHT deposits right_part at right_pad, clears event, departs.
    3. LEFT waits for right_ready, moves to right_pad, grasps right_part, moves to left_target, releases, clears right_ready.
    4. RIGHT waits for left_ready, moves to left_pad, grasps left_part, moves to right_target, releases, clears left_ready.
    5. Both arms move to their respective departure poses.
    """
    
    # Constants
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    # Objects
    OBJ_LEFT = "left_part"
    OBJ_RIGHT = "right_part"
    
    # Poses
    POSE_L_HOME = "left_home"
    POSE_R_HOME = "right_home"
    POSE_L_SOURCE = "left_source"
    POSE_R_SOURCE = "right_source"
    POSE_L_PAD = "left_pad"
    POSE_R_PAD = "right_pad"
    POSE_L_WAIT = "left_pickup_wait"
    POSE_R_WAIT = "right_pickup_wait"
    POSE_L_TARGET = "left_target"
    POSE_R_TARGET = "right_target"
    POSE_L_DEPART = "left_depart"
    POSE_R_DEPART = "right_depart"
    
    # Events
    EVT_L_READY = "left_ready"
    EVT_R_READY = "right_ready"
    
    # --- Phase 1: LEFT Deposit ---
    # Move to source
    await robot.move(ARM_LEFT, POSE_L_SOURCE)
    # Grasp own part
    await robot.grasp(ARM_LEFT, OBJ_LEFT)
    # Move to pad
    await robot.move(ARM_LEFT, POSE_L_PAD)
    # Release part
    await robot.release(ARM_LEFT, OBJ_LEFT, POSE_L_PAD)
    # Signal ready
    l_ready_receipt = robot.signal(EVT_L_READY, OBJ_LEFT)
    # Depart immediately
    await robot.move(ARM_LEFT, POSE_L_DEPART)
    
    # --- Phase 2: RIGHT Deposit ---
    # Move to source
    await robot.move(ARM_RIGHT, POSE_R_SOURCE)
    # Grasp own part
    await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
    # Move to pad
    await robot.move(ARM_RIGHT, POSE_R_PAD)
    # Release part
    await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_R_PAD)
    # Signal ready
    r_ready_receipt = robot.signal(EVT_R_READY, OBJ_RIGHT)
    # Depart immediately
    await robot.move(ARM_RIGHT, POSE_R_DEPART)
    
    # --- Phase 3: LEFT Consumption ---
    # Wait for peer ready
    r_wait_receipt = await robot.wait_event(EVT_R_READY, timeout_s=30)
    # Move to wait pose (approach start)
    await robot.move(ARM_LEFT, POSE_L_WAIT)
    # Move to interaction pose (approach end)
    await robot.move(ARM_LEFT, POSE_R_PAD)
    # Grasp peer item
    await robot.grasp(ARM_LEFT, OBJ_RIGHT)
    # Move to own target carrying the receipt
    await robot.move(ARM_LEFT, POSE_L_TARGET, receipt=r_wait_receipt)
    # Release
    await robot.release(ARM_LEFT, OBJ_RIGHT, POSE_L_TARGET)
    # Clear peer event
    robot.clear_event(EVT_R_READY, expected_version=r_wait_receipt.version)
    
    # --- Phase 4: RIGHT Consumption ---
    # Wait for peer ready
    l_wait_receipt = await robot.wait_event(EVT_L_READY, timeout_s=30)
    # Move to wait pose (approach start)
    await robot.move(ARM_RIGHT, POSE_R_WAIT)
    # Move to interaction pose (approach end)
    await robot.move(ARM_RIGHT, POSE_L_PAD)
    # Grasp peer item
    await robot.grasp(ARM_RIGHT, OBJ_LEFT)
    # Move to own target carrying the receipt
    await robot.move(ARM_RIGHT, POSE_R_TARGET, receipt=l_wait_receipt)
    # Release
    await robot.release(ARM_RIGHT, OBJ_LEFT, POSE_R_TARGET)
    # Clear peer event
    robot.clear_event(EVT_L_READY, expected_version=l_wait_receipt.version)
    
    # --- Phase 5: Final Departure ---
    # Both arms move to final departure poses
    await robot.move(ARM_LEFT, POSE_L_DEPART)
    await robot.move(ARM_RIGHT, POSE_R_DEPART)
