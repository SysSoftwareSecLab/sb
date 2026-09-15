import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    
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

    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"

    # --- Helper Functions ---

    async def acquire_tool(arm: str):
        await robot.acquire(arm, TOOL, 120.0)

    async def release_tool(arm: str):
        await robot.set_mode(arm, TOOL, "OFF")
        await robot.release_resource(arm, TOOL)

    async def acquire_buffer_lock(arm: str):
        await robot.acquire(arm, BUFFER_LOCK, 120.0)

    async def release_buffer_lock(arm: str):
        await robot.set_mode(arm, BUFFER_LOCK, "OFF")
        await robot.release_resource(arm, BUFFER_LOCK)

    # --- Episode 0: part_0 ---

    # Producer (LEFT)
    async def producer_episode_0():
        await acquire_tool(LEFT)
        
        # Approach and Grasp part_0
        await robot.move(LEFT, SOURCE_0)
        obs_p0 = await robot.grasp(LEFT, PART_0)
        
        # Acquire buffer lock
        await acquire_buffer_lock(LEFT)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_0)
        
        # Release part_0 at buffer
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # Depart buffer (immediate separating departure)
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer lock
        await release_buffer_lock(LEFT)
        
        # Publish ready_0
        receipt_ready_0 = robot.signal(READY_0, PART_0)
        
        # Release tool
        await release_tool(LEFT)
        
        return receipt_ready_0

    # Consumer (RIGHT)
    async def consumer_episode_0():
        # Wait for ready_0
        receipt_ready_0 = await robot.wait_event(READY_0, 120.0)
        
        await acquire_tool(RIGHT)
        
        # Acquire buffer lock
        await acquire_buffer_lock(RIGHT)
        
        # Approach and Grasp part_0
        await robot.move(RIGHT, BUFFER_0)
        obs_p0 = await robot.grasp(RIGHT, PART_0)
        
        # Depart buffer (immediate separating departure)
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer lock
        await release_buffer_lock(RIGHT)
        
        # Carried move to target_0 with receipt
        await robot.move(RIGHT, TARGET_0, receipt=receipt_ready_0)
        
        # Clear ready_0
        robot.clear_event(READY_0, expected_version=receipt_ready_0.version)
        
        # Release part_0 at target
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Publish empty_0
        robot.signal(EMPTY_0)
        
        # Release tool
        await release_tool(RIGHT)

    # Run Episode 0 (Serial)
    await producer_episode_0()
    await consumer_episode_0()

    # --- Episode 1: part_1 ---

    # Producer (LEFT)
    async def producer_episode_1():
        # Wait and clear empty_0
        receipt_empty_0 = await robot.wait_event(EMPTY_0, 120.0)
        robot.clear_event(EMPTY_0, expected_version=receipt_empty_0.version)
        
        await acquire_tool(LEFT)
        
        # Approach and Grasp part_1
        await robot.move(LEFT, SOURCE_1)
        obs_p1 = await robot.grasp(LEFT, PART_1)
        
        # Acquire buffer lock
        await acquire_buffer_lock(LEFT)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_1)
        
        # Release part_1 at buffer
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # Depart buffer
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer lock
        await release_buffer_lock(LEFT)
        
        # Publish ready_1
        receipt_ready_1 = robot.signal(READY_1, PART_1)
        
        # Release tool
        await release_tool(LEFT)
        
        return receipt_ready_1

    # Consumer (RIGHT)
    async def consumer_episode_1():
        # Wait for ready_1
        receipt_ready_1 = await robot.wait_event(READY_1, 120.0)
        
        await acquire_tool(RIGHT)
        
        # Acquire buffer lock
        await acquire_buffer_lock(RIGHT)
        
        # Approach and Grasp part_1
        await robot.move(RIGHT, BUFFER_1)
        obs_p1 = await robot.grasp(RIGHT, PART_1)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer lock
        await release_buffer_lock(RIGHT)
        
        # Carried move to target_1 with receipt
        await robot.move(RIGHT, TARGET_1, receipt=receipt_ready_1)
        
        # Clear ready_1
        robot.clear_event(READY_1, expected_version=receipt_ready_1.version)
        
        # Release part_1 at target
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Publish empty_0 (Final state requires events inactive, but goal says "events inactive" usually implies cleared. 
        # However, goal string says "events inactive", and empty_0 is program_clearable. 
        # The consumer publishes empty_0 after release. 
        # Wait, goal says "events inactive". Usually means cleared. 
        # But consumer publishes empty_0. 
        # Let's check goal: "part_0 at target_0; part_1 at target_1; empty arms at homes; buffer empty; lock free; events inactive".
        # If I signal empty_0, it becomes active. 
        # Maybe I should not signal it? 
        # But "Consumer ... releases on target and departs before publishing empty_0." is in required_order.
        # And "Producer waits and clears empty_0...".
        # If I signal it, it is active. 
        # Maybe "events inactive" applies to ready events? 
        # Or maybe I signal it and then clear it? 
        # But Producer waits for it. 
        # If I clear it, Producer can't wait for it (wait_event waits for active).
        # So I must signal it. 
        # Perhaps "events inactive" in goal is a generic template or implies ready events are cleared.
        # I will follow required_order strictly.
        robot.signal(EMPTY_0)
        
        # Release tool
        await release_tool(RIGHT)

    # Run Episode 1 (Serial)
    await producer_episode_1()
    await consumer_episode_1()
