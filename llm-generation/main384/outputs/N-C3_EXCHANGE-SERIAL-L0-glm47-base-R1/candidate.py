import asyncio

async def run_task(robot):
    """
    Executes the C3_EXCHANGE task with Variant A (Serial execution).
    Sequence:
    1. LEFT deposits left_part at left_pad, clears pad, signals left_ready.
    2. RIGHT deposits right_part at right_pad, clears pad, signals right_ready.
    3. RIGHT waits for left_ready, picks up left_part, moves to left_target (carrying receipt), clears left_ready.
    4. LEFT waits for right_ready, picks up right_part, moves to right_target (carrying receipt), clears right_ready.
    5. Both arms move to departure poses.
    """

    # Constants
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    OBJ_LEFT = "left_part"
    OBJ_RIGHT = "right_part"
    
    POSE_LEFT_HOME = "left_home"
    POSE_RIGHT_HOME = "right_home"
    
    POSE_LEFT_SOURCE = "left_source"
    POSE_RIGHT_SOURCE = "right_source"
    
    POSE_LEFT_PAD = "left_pad"
    POSE_RIGHT_PAD = "right_pad"
    
    POSE_LEFT_TARGET = "left_target"
    POSE_RIGHT_TARGET = "right_target"
    
    POSE_LEFT_DEPART = "left_depart"
    POSE_RIGHT_DEPART = "right_depart"
    
    POSE_LEFT_CLEAR = "left_clear"
    POSE_RIGHT_CLEAR = "right_clear"
    
    POSE_LEFT_PICKUP_WAIT = "left_pickup_wait"
    POSE_RIGHT_PICKUP_WAIT = "right_pickup_wait"
    
    EVENT_LEFT_READY = "left_ready"
    EVENT_RIGHT_READY = "right_ready"
    
    TIMEOUT_S = 4.0

    # --- Phase 1: LEFT Deposit ---
    
    # 1.1 Move to source and grasp left_part
    await robot.move(ARM_LEFT, POSE_LEFT_SOURCE, timeout_s=TIMEOUT_S)
    await robot.grasp(ARM_LEFT, OBJ_LEFT)
    
    # 1.2 Move to pad and release
    await robot.move(ARM_LEFT, POSE_LEFT_PAD, timeout_s=TIMEOUT_S)
    await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_PAD)
    
    # 1.3 Clear pad immediately
    await robot.move(ARM_LEFT, POSE_LEFT_CLEAR, timeout_s=TIMEOUT_S)
    
    # 1.4 Signal left_ready
    receipt_left_ready = robot.signal(EVENT_LEFT_READY, item_id=OBJ_LEFT)

    # --- Phase 2: RIGHT Deposit ---
    
    # 2.1 Move to source and grasp right_part
    await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE, timeout_s=TIMEOUT_S)
    await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
    
    # 2.2 Move to pad and release
    await robot.move(ARM_RIGHT, POSE_RIGHT_PAD, timeout_s=TIMEOUT_S)
    await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_PAD)
    
    # 2.3 Clear pad immediately
    await robot.move(ARM_RIGHT, POSE_RIGHT_CLEAR, timeout_s=TIMEOUT_S)
    
    # 2.4 Signal right_ready
    receipt_right_ready = robot.signal(EVENT_RIGHT_READY, item_id=OBJ_RIGHT)

    # --- Phase 3: RIGHT Consumes LEFT ---
    
    # 3.1 Wait for left_ready
    wait_left_receipt = await robot.wait_event(EVENT_LEFT_READY, timeout_s=TIMEOUT_S)
    
    # 3.2 Move to pickup wait pose
    await robot.move(ARM_RIGHT, POSE_RIGHT_PICKUP_WAIT, timeout_s=TIMEOUT_S)
    
    # 3.3 Approach and grasp left_part
    await robot.move(ARM_RIGHT, POSE_LEFT_PAD, timeout_s=TIMEOUT_S)
    await robot.grasp(ARM_RIGHT, OBJ_LEFT)
    
    # 3.4 Move to target carrying the receipt
    await robot.move(ARM_RIGHT, POSE_LEFT_TARGET, timeout_s=TIMEOUT_S, receipt=wait_left_receipt)
    
    # 3.5 Release and clear event
    await robot.release(ARM_RIGHT, OBJ_LEFT, POSE_LEFT_TARGET)
    robot.clear_event(EVENT_LEFT_READY, expected_version=wait_left_receipt.version)

    # --- Phase 4: LEFT Consumes RIGHT ---
    
    # 4.1 Wait for right_ready
    wait_right_receipt = await robot.wait_event(EVENT_RIGHT_READY, timeout_s=TIMEOUT_S)
    
    # 4.2 Move to pickup wait pose
    await robot.move(ARM_LEFT, POSE_LEFT_PICKUP_WAIT, timeout_s=TIMEOUT_S)
    
    # 4.3 Approach and grasp right_part
    await robot.move(ARM_LEFT, POSE_RIGHT_PAD, timeout_s=TIMEOUT_S)
    await robot.grasp(ARM_LEFT, OBJ_RIGHT)
    
    # 4.4 Move to target carrying the receipt
    await robot.move(ARM_LEFT, POSE_RIGHT_TARGET, timeout_s=TIMEOUT_S, receipt=wait_right_receipt)
    
    # 4.5 Release and clear event
    await robot.release(ARM_LEFT, OBJ_RIGHT, POSE_RIGHT_TARGET)
    robot.clear_event(EVENT_RIGHT_READY, expected_version=wait_right_receipt.version)

    # --- Phase 5: Departure ---
    
    # Move to final departure poses
    await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_S)
    await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART, timeout_s=TIMEOUT_S)
