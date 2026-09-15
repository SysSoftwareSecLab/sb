import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants from task spec
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Objects
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
    
    # Resources
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"
    
    # Helper to clear event
    def clear_event_sync(event_id: str, receipt: EventReceipt):
        robot.clear_event(event_id, expected_version=receipt.version)

    async def producer():
        # --- Episode 1: Part 0 ---
        
        # 1. Acquire tool
        await robot.acquire(LEFT, TOOL, timeout_s=10)
        
        # 2. Move to source_0 (Approach)
        await robot.move(LEFT, SOURCE_0)
        
        # 3. Grasp part_0
        await robot.grasp(LEFT, PART_0)
        
        # 4. Move to buffer_0
        await robot.acquire(LEFT, BUFFER_LOCK, timeout_s=10)
        await robot.move(LEFT, BUFFER_0)
        
        # 5. Release part_0 at buffer_0
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # 6. Depart buffer (Immediate departure)
        await robot.move(LEFT, LEFT_WAIT)
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 7. Publish ready_0
        ready_0_receipt = robot.signal(READY_0, item_id=PART_0)
        
        # 8. Release tool
        await robot.release_resource(LEFT, TOOL)
        
        # --- Episode 2: Part 1 ---
        
        # 1. Wait and clear empty_0
        empty_0_receipt = await robot.wait_event(EMPTY_0, timeout_s=50)
        clear_event_sync(EMPTY_0, empty_0_receipt)
        
        # 2. Acquire tool
        await robot.acquire(LEFT, TOOL, timeout_s=10)
        
        # 3. Move to source_1 (Approach)
        await robot.move(LEFT, SOURCE_1)
        
        # 4. Grasp part_1
        await robot.grasp(LEFT, PART_1)
        
        # 5. Move to buffer_1
        await robot.acquire(LEFT, BUFFER_LOCK, timeout_s=10)
        await robot.move(LEFT, BUFFER_1)
        
        # 6. Release part_1 at buffer_1
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # 7. Depart buffer
        await robot.move(LEFT, LEFT_HOME)
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 8. Publish ready_1
        robot.signal(READY_1, item_id=PART_1)
        
        # 9. Release tool
        await robot.release_resource(LEFT, TOOL)

    async def consumer():
        # --- Episode 1: Part 0 ---
        
        # 1. Wait ready_0
        ready_0_receipt = await robot.wait_event(READY_0, timeout_s=50)
        
        # 2. Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, timeout_s=10)
        
        # 3. Move to buffer_0 (Approach)
        await robot.move(RIGHT, BUFFER_0)
        
        # 4. Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # 5. Depart buffer
        await robot.move(RIGHT, RIGHT_WAIT)
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 6. Move to target_0 (Carried move with receipt)
        await robot.move(RIGHT, TARGET_0, receipt=ready_0_receipt)
        
        # 7. Clear ready_0
        clear_event_sync(READY_0, ready_0_receipt)
        
        # 8. Release part_0
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # 9. Depart target
        await robot.move(RIGHT, RIGHT_HOME)
        
        # 10. Publish empty_0
        robot.signal(EMPTY_0)
        
        # --- Episode 2: Part 1 ---
        
        # 1. Wait ready_1
        ready_1_receipt = await robot.wait_event(READY_1, timeout_s=50)
        
        # 2. Inspect both readiness facts (Joined inside loop branch)
        # "For item 1, wait and clear empty_0, then inspect both readiness facts"
        # Note: empty_0 is already cleared by producer before signaling ready_1.
        # We perform the inspections here.
        obs_line_clear = await robot.inspect(RIGHT, FACT_LINE_CLEAR)
        obs_receiver_ready = await robot.inspect(RIGHT, FACT_RECEIVER_READY)
        
        # 3. Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, timeout_s=10)
        
        # 4. Move to buffer_1 (Approach)
        await robot.move(RIGHT, BUFFER_1)
        
        # 5. Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # 6. Depart buffer
        await robot.move(RIGHT, RIGHT_WAIT)
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 7. Move to target_1 (Carried move with receipt)
        await robot.move(RIGHT, TARGET_1, receipt=ready_1_receipt)
        
        # 8. Clear ready_1
        clear_event_sync(READY_1, ready_1_receipt)
        
        # 9. Release part_1
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # 10. Depart target
        await robot.move(RIGHT, RIGHT_HOME)

    # Run producer and consumer coroutines together
    await asyncio.gather(producer(), consumer())
