import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants derived from PUBLIC TASK
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_SOURCE = "left_source"
    LEFT_PAD = "left_pad"
    LEFT_PICKUP_WAIT = "left_pickup_wait"
    LEFT_TARGET = "left_target"
    LEFT_DEPART = "left_depart"
    
    RIGHT_HOME = "right_home"
    RIGHT_SOURCE = "right_source"
    RIGHT_PAD = "right_pad"
    RIGHT_PICKUP_WAIT = "right_pickup_wait"
    RIGHT_TARGET = "right_target"
    RIGHT_DEPART = "right_depart"
    
    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    
    # Timeout
    TIMEOUT = 30.0

    async def left_worker():
        # 1. Deposit own item
        # Approach LEFT_PART at LEFT_SOURCE from LEFT_HOME
        await robot.move(LEFT, LEFT_SOURCE, timeout_s=TIMEOUT)
        # Grasp LEFT_PART
        await robot.grasp(LEFT, LEFT_PART)
        # Move to LEFT_PAD
        await robot.move(LEFT, LEFT_PAD, timeout_s=TIMEOUT)
        # Release LEFT_PART at LEFT_PAD
        await robot.release(LEFT, LEFT_PART, LEFT_PAD)
        # Immediate departure: clear the pad
        await robot.move(LEFT, LEFT_DEPART, timeout_s=TIMEOUT)
        
        # 2. Publish own ready event
        # Signal LEFT_READY (item_id=None as per "own item-bound ready event" implies generic arm readiness or item context)
        # The prompt says "publishing its own item-bound ready event".
        # Given the receipt usage later, we signal the event.
        left_receipt = robot.signal(LEFT_READY, item_id=LEFT_PART)
        
        # 3. Wait for peer ready
        # Wait for RIGHT_READY
        right_receipt = await robot.wait_event(RIGHT_READY, timeout_s=TIMEOUT)
        
        # 4. Consume peer item
        # Move to pickup wait pose for RIGHT_PART
        await robot.move(LEFT, LEFT_PICKUP_WAIT, timeout_s=TIMEOUT)
        # Approach RIGHT_PART at RIGHT_PAD
        await robot.move(LEFT, RIGHT_PAD, timeout_s=TIMEOUT)
        # Grasp RIGHT_PART
        await robot.grasp(LEFT, RIGHT_PART)
        
        # 5. Carried move to own target using peer receipt
        # Move to LEFT_TARGET carrying RIGHT_PART, using right_receipt
        await robot.move(LEFT, LEFT_TARGET, timeout_s=TIMEOUT, receipt=right_receipt)
        
        # 6. Clear peer event after move
        # Clear RIGHT_READY
        robot.clear_event(RIGHT_READY, expected_version=right_receipt.version)
        
        # 7. Deposit peer item
        # Release RIGHT_PART at LEFT_TARGET
        await robot.release(LEFT, RIGHT_PART, LEFT_TARGET)
        
        # 8. Final departure
        # Move to LEFT_DEPART (already there, but ensure terminal obligation)
        await robot.move(LEFT, LEFT_DEPART, timeout_s=TIMEOUT)

    async def right_worker():
        # 1. Deposit own item
        # Approach RIGHT_PART at RIGHT_SOURCE from RIGHT_HOME
        await robot.move(RIGHT, RIGHT_SOURCE, timeout_s=TIMEOUT)
        # Grasp RIGHT_PART
        await robot.grasp(RIGHT, RIGHT_PART)
        # Move to RIGHT_PAD
        await robot.move(RIGHT, RIGHT_PAD, timeout_s=TIMEOUT)
        # Release RIGHT_PART at RIGHT_PAD
        await robot.release(RIGHT, RIGHT_PART, RIGHT_PAD)
        # Immediate departure: clear the pad
        await robot.move(RIGHT, RIGHT_DEPART, timeout_s=TIMEOUT)
        
        # 2. Publish own ready event
        right_receipt = robot.signal(RIGHT_READY, item_id=RIGHT_PART)
        
        # 3. Wait for peer ready
        # Wait for LEFT_READY
        left_receipt = await robot.wait_event(LEFT_READY, timeout_s=TIMEOUT)
        
        # 4. Consume peer item
        # Move to pickup wait pose for LEFT_PART
        await robot.move(RIGHT, RIGHT_PICKUP_WAIT, timeout_s=TIMEOUT)
        # Approach LEFT_PART at LEFT_PAD
        await robot.move(RIGHT, LEFT_PAD, timeout_s=TIMEOUT)
        # Grasp LEFT_PART
        await robot.grasp(RIGHT, LEFT_PART)
        
        # 5. Carried move to own target using peer receipt
        # Move to RIGHT_TARGET carrying LEFT_PART, using left_receipt
        await robot.move(RIGHT, RIGHT_TARGET, timeout_s=TIMEOUT, receipt=left_receipt)
        
        # 6. Clear peer event after move
        # Clear LEFT_READY
        robot.clear_event(LEFT_READY, expected_version=left_receipt.version)
        
        # 7. Deposit peer item
        # Release LEFT_PART at RIGHT_TARGET
        await robot.release(RIGHT, LEFT_PART, RIGHT_TARGET)
        
        # 8. Final departure
        # Move to RIGHT_DEPART (already there, but ensure terminal obligation)
        await robot.move(RIGHT, RIGHT_DEPART, timeout_s=TIMEOUT)

    # Run both workers concurrently
    await asyncio.gather(left_worker(), right_worker())
