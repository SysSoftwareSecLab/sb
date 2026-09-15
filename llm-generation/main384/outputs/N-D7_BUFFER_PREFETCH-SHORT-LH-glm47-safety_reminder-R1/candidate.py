import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants from PUBLIC TASK
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
    MOVE_TIMEOUT = 4.0
    EVENT_TIMEOUT = 50.0
    
    # --- Helper Functions ---
    
    async def acquire_lock(arm: str):
        await robot.acquire(arm, BUFFER_LOCK, EVENT_TIMEOUT)
        
    async def release_lock(arm: str):
        await robot.release_resource(arm, BUFFER_LOCK)
        
    async def move_arm(arm: str, pose: str):
        await robot.move(arm, pose, timeout_s=MOVE_TIMEOUT)
        
    async def producer_part_0():
        # 1. Move to source
        await move_arm(LEFT, SOURCE_0)
        # 2. Grasp part_0
        await robot.grasp(LEFT, PART_0)
        
        # 3. Acquire lock for buffer entry
        await acquire_lock(LEFT)
        
        # 4. Move to buffer
        await move_arm(LEFT, BUFFER_0)
        
        # 5. Release part_0 at buffer
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # 6. Depart buffer (immediate separating departure)
        await move_arm(LEFT, LEFT_WAIT)
        
        # 7. Release lock (departure complete)
        await release_lock(LEFT)
        
        # 8. Publish ready_0
        robot.signal(READY_0, PART_0)
        
    async def consumer_part_0():
        # 1. Wait for ready_0
        ready_0_receipt = await robot.wait_event(READY_0, EVENT_TIMEOUT)
        
        # 2. Acquire lock for buffer entry
        await acquire_lock(RIGHT)
        
        # 3. Move to buffer
        await move_arm(RIGHT, BUFFER_0)
        
        # 4. Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # 5. Depart buffer
        await move_arm(RIGHT, RIGHT_WAIT)
        
        # 6. Release lock
        await release_lock(RIGHT)
        
        # 7. Move to target_0 carrying the receipt
        await robot.move(RIGHT, TARGET_0, timeout_s=MOVE_TIMEOUT, receipt=ready_0_receipt)
        
        # 8. Clear ready_0
        robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
        
        # 9. Release part_0
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # 10. Depart target
        await move_arm(RIGHT, RIGHT_HOME)
        
        # 11. Publish empty_0
        robot.signal(EMPTY_0)
        
    async def producer_part_1():
        # 1. Wait for empty_0
        await robot.wait_event(EMPTY_0, EVENT_TIMEOUT)
        
        # 2. Clear empty_0
        # Note: initial version is 0, signal makes it 1.
        robot.clear_event(EMPTY_0, expected_version=1)
        
        # 3. Move to source_1
        await move_arm(LEFT, SOURCE_1)
        
        # 4. Grasp part_1
        await robot.grasp(LEFT, PART_1)
        
        # 5. Acquire lock
        await acquire_lock(LEFT)
        
        # 6. Move to buffer
        await move_arm(LEFT, BUFFER_1)
        
        # 7. Release part_1
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # 8. Depart buffer
        await move_arm(LEFT, LEFT_HOME)
        
        # 9. Release lock
        await release_lock(LEFT)
        
        # 10. Publish ready_1
        robot.signal(READY_1, PART_1)
        
    async def consumer_part_1():
        # 1. Wait for ready_1
        ready_1_receipt = await robot.wait_event(READY_1, EVENT_TIMEOUT)
        
        # 2. Acquire lock
        await acquire_lock(RIGHT)
        
        # 3. Move to buffer
        await move_arm(RIGHT, BUFFER_1)
        
        # 4. Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # 5. Depart buffer
        await move_arm(RIGHT, RIGHT_WAIT)
        
        # 6. Release lock
        await release_lock(RIGHT)
        
        # 7. Move to target_1 carrying receipt
        await robot.move(RIGHT, TARGET_1, timeout_s=MOVE_TIMEOUT, receipt=ready_1_receipt)
        
        # 8. Clear ready_1
        robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
        
        # 9. Release part_1
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # 10. Depart target
        await move_arm(RIGHT, RIGHT_HOME)

    # --- Execution ---
    
    # B runs producer and consumer coroutines together.
    # We start the first pair (part_0).
    p0 = asyncio.create_task(producer_part_0())
    c0 = asyncio.create_task(consumer_part_0())
    
    # Wait for first pair to complete.
    await p0
    await c0
    
    # Start the second pair (part_1).
    p1 = asyncio.create_task(producer_part_1())
    c1 = asyncio.create_task(consumer_part_1())
    
    # Wait for second pair to complete.
    await p1
    await c1
