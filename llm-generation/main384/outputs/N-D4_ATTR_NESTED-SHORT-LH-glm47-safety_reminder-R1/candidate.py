import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    PART_0 = "part_0"
    PART_1 = "part_1"
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    
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

    async def producer():
        # Episode 1: part_0
        # Move to source
        await robot.move(LEFT, SOURCE_0)
        # Grasp part_0
        await robot.grasp(LEFT, PART_0)
        
        # Acquire tool for buffer placement
        await robot.acquire(LEFT, TOOL, 4.0)
        await robot.set_mode(LEFT, TOOL, "LEFT_PROFILE")
        
        # Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, 4.0)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_0)
        # Release part_0
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # Depart buffer (immediate separating departure)
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Release tool
        await robot.set_mode(LEFT, TOOL, "OFF")
        await robot.release_resource(LEFT, TOOL)
        
        # Signal ready_0
        robot.signal(READY_0, PART_0)
        
        # Episode 2: part_1
        # Wait for empty_0
        empty_receipt = await robot.wait_event(EMPTY_0, 4.0)
        # Clear empty_0
        robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)
        
        # Move to source
        await robot.move(LEFT, SOURCE_1)
        # Grasp part_1
        await robot.grasp(LEFT, PART_1)
        
        # Acquire tool for buffer placement
        await robot.acquire(LEFT, TOOL, 4.0)
        await robot.set_mode(LEFT, TOOL, "LEFT_PROFILE")
        
        # Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, 4.0)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_1)
        # Release part_1
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # Depart buffer
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Release tool
        await robot.set_mode(LEFT, TOOL, "OFF")
        await robot.release_resource(LEFT, TOOL)
        
        # Signal ready_1
        robot.signal(READY_1, PART_1)

    async def consumer():
        # Episode 1: part_0
        # Wait for ready_0
        ready_0_receipt = await robot.wait_event(READY_0, 4.0)
        
        # Move to buffer
        await robot.move(RIGHT, BUFFER_0)
        # Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # Move to target using receipt
        await robot.move(RIGHT, TARGET_0, receipt=ready_0_receipt)
        
        # Clear ready_0
        robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
        
        # Release part_0
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Signal empty_0
        robot.signal(EMPTY_0)
        
        # Episode 2: part_1
        # Wait for ready_1
        ready_1_receipt = await robot.wait_event(READY_1, 4.0)
        
        # Move to buffer
        await robot.move(RIGHT, BUFFER_1)
        # Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # Move to target using receipt
        await robot.move(RIGHT, TARGET_1, receipt=ready_1_receipt)
        
        # Clear ready_1
        robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
        
        # Release part_1
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME)

    # Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())
