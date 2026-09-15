import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants from task spec
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
    
    async def producer_part_0():
        # 1. Move to source
        await robot.move(LEFT, SOURCE_0, timeout_s=TIMEOUT_S)
        # 2. Grasp part_0
        obs0 = await robot.grasp(LEFT, PART_0)
        
        # 3. Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        
        # 4. Move to buffer
        await robot.move(LEFT, BUFFER_0, timeout_s=TIMEOUT_S)
        
        # 5. Release part_0 at buffer
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # 6. Depart immediately (move to wait)
        await robot.move(LEFT, LEFT_WAIT, timeout_s=TIMEOUT_S)
        
        # 7. Signal ready_0
        receipt_ready_0 = robot.signal(READY_0, item_id=PART_0)
        
        # 8. Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        return receipt_ready_0

    async def consumer_part_0():
        # 1. Wait for ready_0
        receipt_ready_0 = await robot.wait_event(READY_0, TIMEOUT_S)
        
        # 2. Acquire buffer lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # 3. Move to buffer
        await robot.move(RIGHT, BUFFER_0, timeout_s=TIMEOUT_S)
        
        # 4. Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # 5. Depart immediately (move to wait)
        await robot.move(RIGHT, RIGHT_WAIT, timeout_s=TIMEOUT_S)
        
        # 6. Release buffer lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 7. Move to target with receipt
        await robot.move(RIGHT, TARGET_0, timeout_s=TIMEOUT_S, receipt=receipt_ready_0)
        
        # 8. Clear ready_0
        robot.clear_event(READY_0, expected_version=receipt_ready_0.version)
        
        # 9. Release part_0 at target
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # 10. Depart immediately (move to home)
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # 11. Signal empty_0
        robot.signal(EMPTY_0)

    async def producer_part_1():
        # 1. Wait for empty_0
        await robot.wait_event(EMPTY_0, TIMEOUT_S)
        
        # 2. Clear empty_0
        # Initial version is 0, so expected is 1 after first signal
        robot.clear_event(EMPTY_0, expected_version=1)
        
        # 3. Move to source
        await robot.move(LEFT, SOURCE_1, timeout_s=TIMEOUT_S)
        
        # 4. Grasp part_1
        obs1 = await robot.grasp(LEFT, PART_1)
        
        # 5. Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        
        # 6. Move to buffer
        await robot.move(LEFT, BUFFER_1, timeout_s=TIMEOUT_S)
        
        # 7. Release part_1 at buffer
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # 8. Depart immediately (move to home)
        await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_S)
        
        # 9. Signal ready_1
        receipt_ready_1 = robot.signal(READY_1, item_id=PART_1)
        
        # 10. Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)

    async def consumer_part_1():
        # 1. Wait for ready_1
        receipt_ready_1 = await robot.wait_event(READY_1, TIMEOUT_S)
        
        # 2. Acquire buffer lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # 3. Move to buffer
        await robot.move(RIGHT, BUFFER_1, timeout_s=TIMEOUT_S)
        
        # 4. Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # 5. Depart immediately (move to home)
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # 6. Release buffer lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 7. Move to target with receipt
        await robot.move(RIGHT, TARGET_1, timeout_s=TIMEOUT_S, receipt=receipt_ready_1)
        
        # 8. Clear ready_1
        robot.clear_event(READY_1, expected_version=receipt_ready_1.version)
        
        # 9. Release part_1 at target
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # 10. Depart immediately (already at home, but ensure state)
        # No move needed if already at home, but spec says "depart before publishing".
        # Since we are at home, we are done.

    # Execute concurrently as per Variant B
    await asyncio.gather(
        producer_part_0(),
        consumer_part_0(),
        producer_part_1(),
        consumer_part_1()
    )
