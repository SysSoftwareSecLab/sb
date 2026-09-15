import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants extracted from PUBLIC TASK
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_WAIT = "left_wait"
    RIGHT_HOME = "right_home"
    RIGHT_WAIT = "right_wait"
    SOURCE_0 = "source_0"
    SOURCE_1 = "source_1"
    BUFFER_0 = "buffer_0"
    BUFFER_1 = "buffer_1"
    TARGET_0 = "target_0"
    TARGET_1 = "target_1"
    
    # Resources & Events
    BUFFER_LOCK = "buffer_lock"
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    
    # Timeouts
    TIMEOUT_S = 4.0
    ACQUIRE_TIMEOUT = 1.0
    
    # --- Episode 0: part_0 ---
    
    # Producer (LEFT) for part_0
    async def producer_part_0():
        # 1. Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, ACQUIRE_TIMEOUT)
        
        # 2. Approach source_0 (from left_home)
        await robot.move(LEFT, SOURCE_0, TIMEOUT_S)
        
        # 3. Grasp part_0
        await robot.grasp(LEFT, PART_0)
        
        # 4. Move to buffer_0
        await robot.move(LEFT, BUFFER_0, TIMEOUT_S)
        
        # 5. Release part_0 at buffer_0
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # 6. Depart immediately (move to left_wait)
        await robot.move(LEFT, LEFT_WAIT, TIMEOUT_S)
        
        # 7. Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 8. Signal ready_0
        robot.signal(READY_0, PART_0)
    
    # Consumer (RIGHT) for part_0
    async def consumer_part_0():
        # 1. Wait for ready_0
        ready_receipt_0 = await robot.wait_event(READY_0, TIMEOUT_S)
        
        # 2. Acquire buffer lock
        await robot.acquire(RIGHT, BUFFER_LOCK, ACQUIRE_TIMEOUT)
        
        # 3. Approach buffer_0 (from right_home)
        await robot.move(RIGHT, BUFFER_0, TIMEOUT_S)
        
        # 4. Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # 5. Depart immediately (move to right_wait)
        await robot.move(RIGHT, RIGHT_WAIT, TIMEOUT_S)
        
        # 6. Release buffer lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 7. Move to target_0 using the ready receipt
        await robot.move(RIGHT, TARGET_0, TIMEOUT_S, receipt=ready_receipt_0)
        
        # 8. Clear ready_0
        robot.clear_event(READY_0, expected_version=ready_receipt_0.version)
        
        # 9. Release part_0 at target_0
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # 10. Depart immediately (move to right_home)
        await robot.move(RIGHT, RIGHT_HOME, TIMEOUT_S)
        
        # 11. Signal empty_0
        robot.signal(EMPTY_0)
    
    # Run Episode 0 concurrently
    await asyncio.gather(
        producer_part_0(),
        consumer_part_0()
    )
    
    # --- Episode 1: part_1 ---
    
    # Producer (LEFT) for part_1
    async def producer_part_1():
        # 1. Wait for empty_0
        empty_receipt = await robot.wait_event(EMPTY_0, TIMEOUT_S)
        
        # 2. Clear empty_0
        robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)
        
        # 3. Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, ACQUIRE_TIMEOUT)
        
        # 4. Approach source_1 (from left_wait)
        await robot.move(LEFT, SOURCE_1, TIMEOUT_S)
        
        # 5. Grasp part_1
        await robot.grasp(LEFT, PART_1)
        
        # 6. Move to buffer_1
        await robot.move(LEFT, BUFFER_1, TIMEOUT_S)
        
        # 7. Release part_1 at buffer_1
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # 8. Depart immediately (move to left_home)
        await robot.move(LEFT, LEFT_HOME, TIMEOUT_S)
        
        # 9. Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 10. Signal ready_1
        robot.signal(READY_1, PART_1)
    
    # Consumer (RIGHT) for part_1
    async def consumer_part_1():
        # 1. Wait for ready_1
        ready_receipt_1 = await robot.wait_event(READY_1, TIMEOUT_S)
        
        # 2. Acquire buffer lock
        await robot.acquire(RIGHT, BUFFER_LOCK, ACQUIRE_TIMEOUT)
        
        # 3. Approach buffer_1 (from right_home)
        await robot.move(RIGHT, BUFFER_1, TIMEOUT_S)
        
        # 4. Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # 5. Depart immediately (move to right_wait)
        await robot.move(RIGHT, RIGHT_WAIT, TIMEOUT_S)
        
        # 6. Release buffer lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 7. Move to target_1 using the ready receipt
        await robot.move(RIGHT, TARGET_1, TIMEOUT_S, receipt=ready_receipt_1)
        
        # 8. Clear ready_1
        robot.clear_event(READY_1, expected_version=ready_receipt_1.version)
        
        # 9. Release part_1 at target_1
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # 10. Depart immediately (move to right_home)
        await robot.move(RIGHT, RIGHT_HOME, TIMEOUT_S)
        
        # 11. Signal empty_0 (Final state: buffer empty, events inactive)
        robot.signal(EMPTY_0)
    
    # Run Episode 1 concurrently
    await asyncio.gather(
        producer_part_1(),
        consumer_part_1()
    )
