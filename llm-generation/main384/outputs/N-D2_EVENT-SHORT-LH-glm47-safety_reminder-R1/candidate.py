import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants from task
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
    LEFT_PICKUP_WAIT = "left_pickup_wait"
    RIGHT_PICKUP_WAIT = "right_pickup_wait"
    
    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    
    # Timeout
    TIMEOUT = 30.0

    async def left_arm_logic():
        # 1. Deposit own item
        # Approach
        await robot.move(LEFT, LEFT_SOURCE, timeout_s=TIMEOUT)
        # Grasp
        await robot.grasp(LEFT, LEFT_PART)
        # Move to pad
        await robot.move(LEFT, LEFT_PAD, timeout_s=TIMEOUT)
        # Release
        await robot.release(LEFT, LEFT_PART, LEFT_PAD)
        # Immediate departure
        await robot.move(LEFT, LEFT_PICKUP_WAIT, timeout_s=TIMEOUT)
        
        # 2. Signal ready
        left_ready_receipt = robot.signal(LEFT_READY, LEFT_PART)
        
        # 3. Wait for peer
        peer_ready_receipt = await robot.wait_event(RIGHT_READY, timeout_s=TIMEOUT)
        
        # 4. Consume peer item
        # Approach
        await robot.move(LEFT, RIGHT_PAD, timeout_s=TIMEOUT)
        # Grasp
        await robot.grasp(LEFT, RIGHT_PART)
        # Carried move to own target using peer receipt
        await robot.move(LEFT, LEFT_TARGET, timeout_s=TIMEOUT, receipt=peer_ready_receipt)
        # Release
        await robot.release(LEFT, RIGHT_PART, LEFT_TARGET)
        # Clear peer event
        robot.clear_event(RIGHT_READY, expected_version=peer_ready_receipt.version)
        # Depart
        await robot.move(LEFT, LEFT_DEPART, timeout_s=TIMEOUT)
        
        # 5. Clear own event
        robot.clear_event(LEFT_READY, expected_version=left_ready_receipt.version)

    async def right_arm_logic():
        # 1. Deposit own item
        # Approach
        await robot.move(RIGHT, RIGHT_SOURCE, timeout_s=TIMEOUT)
        # Grasp
        await robot.grasp(RIGHT, RIGHT_PART)
        # Move to pad
        await robot.move(RIGHT, RIGHT_PAD, timeout_s=TIMEOUT)
        # Release
        await robot.release(RIGHT, RIGHT_PART, RIGHT_PAD)
        # Immediate departure
        await robot.move(RIGHT, RIGHT_PICKUP_WAIT, timeout_s=TIMEOUT)
        
        # 2. Signal ready
        right_ready_receipt = robot.signal(RIGHT_READY, RIGHT_PART)
        
        # 3. Wait for peer
        peer_ready_receipt = await robot.wait_event(LEFT_READY, timeout_s=TIMEOUT)
        
        # 4. Consume peer item
        # Approach
        await robot.move(RIGHT, LEFT_PAD, timeout_s=TIMEOUT)
        # Grasp
        await robot.grasp(RIGHT, LEFT_PART)
        # Carried move to own target using peer receipt
        await robot.move(RIGHT, RIGHT_TARGET, timeout_s=TIMEOUT, receipt=peer_ready_receipt)
        # Release
        await robot.release(RIGHT, LEFT_PART, RIGHT_TARGET)
        # Clear peer event
        robot.clear_event(LEFT_READY, expected_version=peer_ready_receipt.version)
        # Depart
        await robot.move(RIGHT, RIGHT_DEPART, timeout_s=TIMEOUT)
        
        # 5. Clear own event
        robot.clear_event(RIGHT_READY, expected_version=right_ready_receipt.version)

    # Run both arms concurrently
    await asyncio.gather(left_arm_logic(), right_arm_logic())
