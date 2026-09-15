import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants derived from PUBLIC TASK
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_SOURCE = "left_source"
    LEFT_PAD = "left_pad"
    LEFT_TARGET = "left_target"
    LEFT_DEPART = "left_depart"
    LEFT_CLEAR = "left_clear"
    
    RIGHT_HOME = "right_home"
    RIGHT_SOURCE = "right_source"
    RIGHT_PAD = "right_pad"
    RIGHT_TARGET = "right_target"
    RIGHT_DEPART = "right_depart"
    RIGHT_CLEAR = "right_clear"
    
    LEFT_PICKUP_WAIT = "left_pickup_wait"
    RIGHT_PICKUP_WAIT = "right_pickup_wait"
    
    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    
    # Timeout
    TIMEOUT = 30.0

    async def left_arm_logic():
        # 1. Deposit own item
        # Approach LEFT_PART at LEFT_SOURCE from LEFT_HOME
        await robot.move(LEFT, LEFT_SOURCE, timeout_s=TIMEOUT)
        # Grasp LEFT_PART
        await robot.grasp(LEFT, LEFT_PART)
        
        # Move to LEFT_PAD
        await robot.move(LEFT, LEFT_PAD, timeout_s=TIMEOUT)
        # Release LEFT_PART at LEFT_PAD
        await robot.release(LEFT, LEFT_PART, LEFT_PAD)
        
        # Immediate departure from LEFT_PAD to LEFT_CLEAR
        await robot.move(LEFT, LEFT_CLEAR, timeout_s=TIMEOUT)
        
        # Publish own ready event (LEFT_READY)
        # Item ID is the object we just deposited (LEFT_PART)
        left_ready_receipt = robot.signal(LEFT_READY, item_id=LEFT_PART)
        
        # 2. Wait for peer ready (RIGHT_READY)
        # Must wait for peer ready event. 
        # The event is bound to the peer item (RIGHT_PART).
        peer_ready_receipt = await robot.wait_event(RIGHT_READY, timeout_s=TIMEOUT)
        
        # 3. Consume peer item
        # Approach RIGHT_PART at RIGHT_PAD from LEFT_PICKUP_WAIT
        # Note: We are currently at LEFT_CLEAR. We must move to the approach start pose.
        await robot.move(LEFT, LEFT_PICKUP_WAIT, timeout_s=TIMEOUT)
        await robot.move(LEFT, RIGHT_PAD, timeout_s=TIMEOUT)
        
        # Grasp RIGHT_PART using the peer receipt
        await robot.grasp(LEFT, RIGHT_PART, observation=peer_ready_receipt)
        
        # Move to LEFT_TARGET carrying the receipt
        await robot.move(LEFT, LEFT_TARGET, timeout_s=TIMEOUT, receipt=peer_ready_receipt)
        
        # Release RIGHT_PART at LEFT_TARGET
        await robot.release(LEFT, RIGHT_PART, LEFT_TARGET)
        
        # Immediate departure from LEFT_TARGET to LEFT_DEPART
        await robot.move(LEFT, LEFT_DEPART, timeout_s=TIMEOUT)
        
        # Clear peer event after the carried move
        robot.clear_event(RIGHT_READY, expected_version=peer_ready_receipt.version)

    async def right_arm_logic():
        # 1. Deposit own item
        # Approach RIGHT_PART at RIGHT_SOURCE from RIGHT_HOME
        await robot.move(RIGHT, RIGHT_SOURCE, timeout_s=TIMEOUT)
        # Grasp RIGHT_PART
        await robot.grasp(RIGHT, RIGHT_PART)
        
        # Move to RIGHT_PAD
        await robot.move(RIGHT, RIGHT_PAD, timeout_s=TIMEOUT)
        # Release RIGHT_PART at RIGHT_PAD
        await robot.release(RIGHT, RIGHT_PART, RIGHT_PAD)
        
        # Immediate departure from RIGHT_PAD to RIGHT_CLEAR
        await robot.move(RIGHT, RIGHT_CLEAR, timeout_s=TIMEOUT)
        
        # Publish own ready event (RIGHT_READY)
        # Item ID is the object we just deposited (RIGHT_PART)
        right_ready_receipt = robot.signal(RIGHT_READY, item_id=RIGHT_PART)
        
        # 2. Wait for peer ready (LEFT_READY)
        # Must wait for peer ready event.
        # The event is bound to the peer item (LEFT_PART).
        peer_ready_receipt = await robot.wait_event(LEFT_READY, timeout_s=TIMEOUT)
        
        # 3. Consume peer item
        # Approach LEFT_PART at LEFT_PAD from RIGHT_PICKUP_WAIT
        # Note: We are currently at RIGHT_CLEAR. We must move to the approach start pose.
        await robot.move(RIGHT, RIGHT_PICKUP_WAIT, timeout_s=TIMEOUT)
        await robot.move(RIGHT, LEFT_PAD, timeout_s=TIMEOUT)
        
        # Grasp LEFT_PART using the peer receipt
        await robot.grasp(RIGHT, LEFT_PART, observation=peer_ready_receipt)
        
        # Move to RIGHT_TARGET carrying the receipt
        await robot.move(RIGHT, RIGHT_TARGET, timeout_s=TIMEOUT, receipt=peer_ready_receipt)
        
        # Release LEFT_PART at RIGHT_TARGET
        await robot.release(RIGHT, LEFT_PART, RIGHT_TARGET)
        
        # Immediate departure from RIGHT_TARGET to RIGHT_DEPART
        await robot.move(RIGHT, RIGHT_DEPART, timeout_s=TIMEOUT)
        
        # Clear peer event after the carried move
        robot.clear_event(LEFT_READY, expected_version=peer_ready_receipt.version)

    # Run both arms concurrently
    await asyncio.gather(left_arm_logic(), right_arm_logic())
