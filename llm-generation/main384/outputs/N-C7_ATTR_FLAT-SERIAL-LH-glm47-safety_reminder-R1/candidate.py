import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    
    # Items
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
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"
    
    # Durations
    TIMEOUT_MOVE = 4.0
    TIMEOUT_EVENT = 10.0
    
    # --- Helper Functions ---
    
    async def acquire_tool(arm: str):
        await robot.acquire(arm, TOOL, TIMEOUT_EVENT)
        await robot.set_mode(arm, TOOL, "LEFT_PROFILE" if arm == LEFT else "RIGHT_PROFILE")
        
    async def release_tool(arm: str):
        await robot.set_mode(arm, TOOL, "OFF")
        await robot.release_resource(arm, TOOL)

    async def acquire_buffer_lock(arm: str):
        await robot.acquire(arm, BUFFER_LOCK, TIMEOUT_EVENT)
        
    async def release_buffer_lock(arm: str):
        await robot.release_resource(arm, BUFFER_LOCK)

    # --- Episode 0: part_0 ---
    
    # Producer (LEFT) for part_0
    async def producer_part_0():
        await acquire_tool(LEFT)
        await acquire_buffer_lock(LEFT)
        
        # Move to source and grasp
        await robot.move(LEFT, SOURCE_0, timeout_s=TIMEOUT_MOVE)
        await robot.grasp(LEFT, PART_0)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_0, timeout_s=TIMEOUT_MOVE)
        
        # Release at buffer
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # Depart immediately
        await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_MOVE)
        
        # Publish ready
        receipt = robot.signal(READY_0, PART_0)
        
        # Release resources
        await release_buffer_lock(LEFT)
        await release_tool(LEFT)
        return receipt

    # Consumer (RIGHT) for part_0
    async def consumer_part_0():
        # Wait for ready
        ready_receipt = await robot.wait_event(READY_0, TIMEOUT_EVENT)
        
        await acquire_buffer_lock(RIGHT)
        
        # Approach and grasp
        await robot.move(RIGHT, BUFFER_0, timeout_s=TIMEOUT_MOVE)
        await robot.grasp(RIGHT, PART_0)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_WAIT, timeout_s=TIMEOUT_MOVE)
        
        # Release lock
        await release_buffer_lock(RIGHT)
        
        # Move to target with receipt
        await robot.move(RIGHT, TARGET_0, timeout_s=TIMEOUT_MOVE, receipt=ready_receipt)
        
        # Clear ready
        robot.clear_event(READY_0, expected_version=ready_receipt.version)
        
        # Release at target
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # Depart
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_MOVE)
        
        # Publish empty
        robot.signal(EMPTY_0)

    # Run Episode 0
    await producer_part_0()
    await consumer_part_0()
    
    # --- Episode 1: part_1 ---
    
    # Producer (LEFT) for part_1
    async def producer_part_1():
        # Wait and clear empty_0
        empty_receipt = await robot.wait_event(EMPTY_0, TIMEOUT_EVENT)
        robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)
        
        await acquire_tool(LEFT)
        await acquire_buffer_lock(LEFT)
        
        # Move to source and grasp
        await robot.move(LEFT, SOURCE_1, timeout_s=TIMEOUT_MOVE)
        await robot.grasp(LEFT, PART_1)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_1, timeout_s=TIMEOUT_MOVE)
        
        # Release at buffer
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # Depart immediately
        await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_MOVE)
        
        # Publish ready
        receipt = robot.signal(READY_1, PART_1)
        
        # Release resources
        await release_buffer_lock(LEFT)
        await release_tool(LEFT)
        return receipt

    # Consumer (RIGHT) for part_1
    async def consumer_part_1():
        # Wait for ready
        ready_receipt = await robot.wait_event(READY_1, TIMEOUT_EVENT)
        
        await acquire_buffer_lock(RIGHT)
        
        # Approach and grasp
        await robot.move(RIGHT, BUFFER_1, timeout_s=TIMEOUT_MOVE)
        await robot.grasp(RIGHT, PART_1)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_WAIT, timeout_s=TIMEOUT_MOVE)
        
        # Release lock
        await release_buffer_lock(RIGHT)
        
        # Move to target with receipt
        await robot.move(RIGHT, TARGET_1, timeout_s=TIMEOUT_MOVE, receipt=ready_receipt)
        
        # Clear ready
        robot.clear_event(READY_1, expected_version=ready_receipt.version)
        
        # Release at target
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # Depart
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_MOVE)
        
        # Publish empty (not strictly required for terminal goal but good practice)
        robot.signal(EMPTY_0)

    # Run Episode 1
    # For item 1, inspect both readiness facts before proceeding
    # "C7 checks serially"
    obs_line = await robot.inspect(LEFT, FACT_LINE_CLEAR)
    obs_recv = await robot.inspect(LEFT, FACT_RECEIVER_READY)
    
    # Verify facts (internal verification logic)
    assert obs_line.value["clear"] == True
    assert obs_line.value["item_id"] == PART_1
    assert obs_recv.value["ready"] == True
    assert obs_recv.value["item_id"] == PART_1
    
    # Execute producer and consumer
    await producer_part_1()
    await consumer_part_1()
