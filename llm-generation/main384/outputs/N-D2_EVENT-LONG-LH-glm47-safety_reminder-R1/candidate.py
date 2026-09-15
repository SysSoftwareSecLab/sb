import asyncio

async def run_task(robot):
    """
    Executes the D2_EVENT-LONG-LH task.
    Strategy:
    1. LEFT moves to left_source, grasps left_part, moves to left_pad, releases left_part, moves to left_clear.
    2. RIGHT moves to right_source, grasps right_part, moves to right_pad, releases right_part, moves to right_clear.
    3. LEFT signals left_ready.
    4. RIGHT signals right_ready.
    5. LEFT waits for right_ready, moves to left_pickup_wait, grasps right_part, moves to left_target, releases right_part, moves to left_depart, clears right_ready.
    6. RIGHT waits for left_ready, moves to right_pickup_wait, grasps left_part, moves to right_target, releases left_part, moves to right_depart, clears left_ready.
    """
    
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_SOURCE = "left_source"
    LEFT_PAD = "left_pad"
    LEFT_CLEAR = "left_clear"
    LEFT_PICKUP_WAIT = "left_pickup_wait"
    LEFT_TARGET = "left_target"
    LEFT_DEPART = "left_depart"
    
    RIGHT_HOME = "right_home"
    RIGHT_SOURCE = "right_source"
    RIGHT_PAD = "right_pad"
    RIGHT_CLEAR = "right_clear"
    RIGHT_PICKUP_WAIT = "right_pickup_wait"
    RIGHT_TARGET = "right_target"
    RIGHT_DEPART = "right_depart"
    
    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    
    # Timeout
    TIMEOUT = 4.0
    
    async def left_arm_logic():
        # 1. Deposit own part
        await robot.move(LEFT, LEFT_SOURCE, timeout_s=TIMEOUT)
        await robot.grasp(LEFT, LEFT_PART)
        await robot.move(LEFT, LEFT_PAD, timeout_s=TIMEOUT)
        await robot.release(LEFT, LEFT_PART, LEFT_PAD)
        
        # Immediate departure
        await robot.move(LEFT, LEFT_CLEAR, timeout_s=TIMEOUT)
        
        # 2. Signal ready
        robot.signal(LEFT_READY)
        
        # 3. Wait for peer
        peer_receipt = await robot.wait_event(RIGHT_READY, timeout_s=TIMEOUT)
        
        # 4. Consume peer item
        await robot.move(LEFT, LEFT_PICKUP_WAIT, timeout_s=TIMEOUT)
        await robot.grasp(LEFT, RIGHT_PART)
        
        # Carried move with receipt
        await robot.move(LEFT, LEFT_TARGET, timeout_s=TIMEOUT, receipt=peer_receipt)
        
        await robot.release(LEFT, RIGHT_PART, LEFT_TARGET)
        
        # 5. Depart and clear
        await robot.move(LEFT, LEFT_DEPART, timeout_s=TIMEOUT)
        robot.clear_event(RIGHT_READY, expected_version=peer_receipt.version)

    async def right_arm_logic():
        # 1. Deposit own part
        await robot.move(RIGHT, RIGHT_SOURCE, timeout_s=TIMEOUT)
        await robot.grasp(RIGHT, RIGHT_PART)
        await robot.move(RIGHT, RIGHT_PAD, timeout_s=TIMEOUT)
        await robot.release(RIGHT, RIGHT_PART, RIGHT_PAD)
        
        # Immediate departure
        await robot.move(RIGHT, RIGHT_CLEAR, timeout_s=TIMEOUT)
        
        # 2. Signal ready
        robot.signal(RIGHT_READY)
        
        # 3. Wait for peer
        peer_receipt = await robot.wait_event(LEFT_READY, timeout_s=TIMEOUT)
        
        # 4. Consume peer item
        await robot.move(RIGHT, RIGHT_PICKUP_WAIT, timeout_s=TIMEOUT)
        await robot.grasp(RIGHT, LEFT_PART)
        
        # Carried move with receipt
        await robot.move(RIGHT, RIGHT_TARGET, timeout_s=TIMEOUT, receipt=peer_receipt)
        
        await robot.release(RIGHT, LEFT_PART, RIGHT_TARGET)
        
        # 5. Depart and clear
        await robot.move(RIGHT, RIGHT_DEPART, timeout_s=TIMEOUT)
        robot.clear_event(LEFT_READY, expected_version=peer_receipt.version)

    # Run both arms concurrently
    await asyncio.gather(left_arm_logic(), right_arm_logic())
