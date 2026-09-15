import asyncio

async def run_task(robot):
    """
    Executes the C3_EXCHANGE task (Variant B: Concurrent Workers).
    Two arms exchange parts via pads.
    Each arm deposits its own part, waits for the peer's ready event,
    then picks up the peer's part and moves to its own target.
    """
    
    # Constants from task spec
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    # Poses
    LEFT_HOME = "left_home"
    RIGHT_HOME = "right_home"
    LEFT_SOURCE = "left_source"
    RIGHT_SOURCE = "right_source"
    LEFT_PAD = "left_pad"
    RIGHT_PAD = "right_pad"
    LEFT_TARGET = "left_target"
    RIGHT_TARGET = "right_target"
    LEFT_DEPART = "left_depart"
    RIGHT_DEPART = "right_depart"
    LEFT_CLEAR = "left_clear"
    RIGHT_CLEAR = "right_clear"
    
    # Events
    EVT_LEFT_READY = "left_ready"
    EVT_RIGHT_READY = "right_ready"
    
    # Timeouts
    MOVE_TIMEOUT = 4.0
    EVENT_TIMEOUT = 30.0

    async def left_worker():
        # 1. Deposit own part (left_part) on left_pad
        # Approach sequence: left_home -> left_source
        await robot.move(LEFT, LEFT_SOURCE, timeout_s=MOVE_TIMEOUT)
        await robot.grasp(LEFT, LEFT_PART)
        
        # Move to pad and release
        await robot.move(LEFT, LEFT_PAD, timeout_s=MOVE_TIMEOUT)
        await robot.release(LEFT, LEFT_PART, LEFT_PAD)
        
        # Immediate departure (clear the pad)
        await robot.move(LEFT, LEFT_CLEAR, timeout_s=MOVE_TIMEOUT)
        
        # Signal own ready event
        receipt = robot.signal(EVT_LEFT_READY, item_id=LEFT_PART)
        
        # 2. Wait for peer ready (right_part)
        peer_receipt = await robot.wait_event(EVT_RIGHT_READY, timeout_s=EVENT_TIMEOUT)
        
        # 3. Consume peer item (right_part) from right_pad
        # Approach sequence: left_pickup_wait -> right_pad
        # Note: We are at left_clear, need to go to left_pickup_wait first? 
        # The approach sequence requires start_pose "left_pickup_wait".
        # We must move to the start pose of the approach sequence.
        await robot.move(LEFT, "left_pickup_wait", timeout_s=MOVE_TIMEOUT)
        
        # Perform approach (move to interaction pose)
        await robot.move(LEFT, RIGHT_PAD, timeout_s=MOVE_TIMEOUT)
        await robot.grasp(LEFT, RIGHT_PART)
        
        # 4. Move to own target (left_target) carrying the peer receipt
        # "The carried move to its own target must carry the exact active peer-item receipt"
        await robot.move(LEFT, LEFT_TARGET, timeout_s=MOVE_TIMEOUT, receipt=peer_receipt)
        
        # 5. Clear the peer event after the move
        robot.clear_event(EVT_RIGHT_READY, expected_version=peer_receipt.version)
        
        # 6. Final departure
        await robot.move(LEFT, LEFT_DEPART, timeout_s=MOVE_TIMEOUT)

    async def right_worker():
        # 1. Deposit own part (right_part) on right_pad
        # Approach sequence: right_home -> right_source
        await robot.move(RIGHT, RIGHT_SOURCE, timeout_s=MOVE_TIMEOUT)
        await robot.grasp(RIGHT, RIGHT_PART)
        
        # Move to pad and release
        await robot.move(RIGHT, RIGHT_PAD, timeout_s=MOVE_TIMEOUT)
        await robot.release(RIGHT, RIGHT_PART, RIGHT_PAD)
        
        # Immediate departure
        await robot.move(RIGHT, RIGHT_CLEAR, timeout_s=MOVE_TIMEOUT)
        
        # Signal own ready event
        receipt = robot.signal(EVT_RIGHT_READY, item_id=RIGHT_PART)
        
        # 2. Wait for peer ready (left_part)
        peer_receipt = await robot.wait_event(EVT_LEFT_READY, timeout_s=EVENT_TIMEOUT)
        
        # 3. Consume peer item (left_part) from left_pad
        # Approach sequence: right_pickup_wait -> left_pad
        await robot.move(RIGHT, "right_pickup_wait", timeout_s=MOVE_TIMEOUT)
        
        await robot.move(RIGHT, LEFT_PAD, timeout_s=MOVE_TIMEOUT)
        await robot.grasp(RIGHT, LEFT_PART)
        
        # 4. Move to own target (right_target) carrying the peer receipt
        await robot.move(RIGHT, RIGHT_TARGET, timeout_s=MOVE_TIMEOUT, receipt=peer_receipt)
        
        # 5. Clear the peer event
        robot.clear_event(EVT_LEFT_READY, expected_version=peer_receipt.version)
        
        # 6. Final departure
        await robot.move(RIGHT, RIGHT_DEPART, timeout_s=MOVE_TIMEOUT)

    # Run both workers concurrently
    await asyncio.gather(left_worker(), right_worker())
