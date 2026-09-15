import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"
    
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
    
    # Items
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    # Timeout
    TIMEOUT = 10.0

    # --- Helper Functions ---
    
    async def acquire_tool(arm: str):
        await robot.acquire(arm, TOOL, TIMEOUT)
        await robot.set_mode(arm, TOOL, "LEFT_PROFILE" if arm == LEFT else "RIGHT_PROFILE")

    async def release_tool(arm: str):
        await robot.set_mode(arm, TOOL, "OFF")
        await robot.release_resource(arm, TOOL)

    async def acquire_buffer_lock(arm: str):
        await robot.acquire(arm, BUFFER_LOCK, TIMEOUT)

    async def release_buffer_lock(arm: str):
        await robot.release_resource(arm, BUFFER_LOCK)

    # --- Producer Coroutine (LEFT) ---
    
    async def producer():
        # --- Episode 1: part_0 ---
        await acquire_tool(LEFT)
        
        # Pick up part_0
        await robot.move(LEFT, SOURCE_0)
        await robot.grasp(LEFT, PART_0)
        
        # Move to buffer
        await acquire_buffer_lock(LEFT)
        await robot.move(LEFT, BUFFER_0)
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # Depart immediately
        await robot.move(LEFT, LEFT_HOME)
        await release_buffer_lock(LEFT)
        
        # Signal ready
        ready_0_receipt = robot.signal(READY_0, PART_0)
        await release_tool(LEFT)
        
        # --- Episode 2: part_1 ---
        # Wait for empty_0
        empty_0_receipt = await robot.wait_event(EMPTY_0, TIMEOUT)
        robot.clear_event(EMPTY_0, expected_version=empty_0_receipt.version)
        
        await acquire_tool(LEFT)
        
        # Pick up part_1
        await robot.move(LEFT, SOURCE_1)
        await robot.grasp(LEFT, PART_1)
        
        # Move to buffer
        await acquire_buffer_lock(LEFT)
        await robot.move(LEFT, BUFFER_1)
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # Depart immediately
        await robot.move(LEFT, LEFT_HOME)
        await release_buffer_lock(LEFT)
        
        # Signal ready
        robot.signal(READY_1, PART_1)
        await release_tool(LEFT)

    # --- Consumer Coroutine (RIGHT) ---
    
    async def consumer():
        # --- Episode 1: part_0 ---
        # Wait for ready_0
        ready_0_receipt = await robot.wait_event(READY_0, TIMEOUT)
        
        await acquire_tool(RIGHT)
        
        # Pick up part_0
        await robot.move(RIGHT, BUFFER_0)
        await robot.grasp(RIGHT, PART_0)
        
        # Move to target using receipt
        await robot.move(RIGHT, TARGET_0, receipt=ready_0_receipt)
        
        # Clear ready after carried move
        robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
        
        # Release and depart
        await robot.release(RIGHT, PART_0, TARGET_0)
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Signal empty
        robot.signal(EMPTY_0)
        await release_tool(RIGHT)
        
        # --- Episode 2: part_1 ---
        # Wait for ready_1
        ready_1_receipt = await robot.wait_event(READY_1, TIMEOUT)
        
        await acquire_tool(RIGHT)
        
        # Pick up part_1
        await robot.move(RIGHT, BUFFER_1)
        await robot.grasp(RIGHT, PART_1)
        
        # Move to target using receipt
        await robot.move(RIGHT, TARGET_1, receipt=ready_1_receipt)
        
        # Clear ready after carried move
        robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
        
        # Release and depart
        await robot.release(RIGHT, PART_1, TARGET_1)
        await robot.move(RIGHT, RIGHT_HOME)
        
        await release_tool(RIGHT)

    # --- Main Execution ---
    
    # Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())
