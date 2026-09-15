import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants extracted from PUBLIC TASK
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
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
    
    # Timeouts
    TIMEOUT_S = 4.0
    ACQUIRE_TIMEOUT = 1.0
    
    # --- Helper Functions ---
    
    async def acquire_tool(arm: str):
        await robot.acquire(arm, TOOL, ACQUIRE_TIMEOUT)
        await robot.set_mode(arm, TOOL, "OFF")
        
    async def release_tool(arm: str):
        await robot.set_mode(arm, TOOL, "OFF")
        await robot.release_resource(arm, TOOL)

    async def acquire_buffer_lock(arm: str):
        await robot.acquire(arm, BUFFER_LOCK, ACQUIRE_TIMEOUT)
        await robot.set_mode(arm, BUFFER_LOCK, "OFF")

    async def release_buffer_lock(arm: str):
        await robot.set_mode(arm, BUFFER_LOCK, "OFF")
        await robot.release_resource(arm, BUFFER_LOCK)

    # --- Episode 0: part_0 ---
    
    # Producer (LEFT) for part_0
    async def producer_part_0():
        # Own tool from before source pickup
        await acquire_tool(LEFT)
        
        # Approach and Grasp part_0
        await robot.move(LEFT, SOURCE_0, timeout_s=TIMEOUT_S)
        await robot.grasp(LEFT, PART_0)
        
        # Own buffer_lock during buffer entry
        await acquire_buffer_lock(LEFT)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_0, timeout_s=TIMEOUT_S)
        
        # Release at buffer
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # Depart immediately (move to left_wait)
        await robot.move(LEFT, LEFT_WAIT, timeout_s=TIMEOUT_S)
        
        # Publish ready_0
        ready_0_receipt = robot.signal(READY_0, PART_0)
        
        # Release buffer_lock after departure
        await release_buffer_lock(LEFT)
        
        # Release tool on exit
        await release_tool(LEFT)
        
        return ready_0_receipt

    # Consumer (RIGHT) for part_0
    async def consumer_part_0():
        # Wait for ready_0
        ready_0_receipt = await robot.wait_event(READY_0, TIMEOUT_S)
        
        # Own buffer_lock during buffer entry
        await acquire_buffer_lock(RIGHT)
        
        # Approach and Grasp part_0
        await robot.move(RIGHT, BUFFER_0, timeout_s=TIMEOUT_S)
        await robot.grasp(RIGHT, PART_0)
        
        # Depart buffer (move to right_wait)
        await robot.move(RIGHT, RIGHT_WAIT, timeout_s=TIMEOUT_S)
        
        # Release buffer_lock after departure
        await release_buffer_lock(RIGHT)
        
        # Carried move to target_0 using ready_0_receipt
        await robot.move(RIGHT, TARGET_0, timeout_s=TIMEOUT_S, receipt=ready_0_receipt)
        
        # Clear ready_0 after carried move
        robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
        
        # Release at target
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # Depart to home
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # Publish empty_0
        robot.signal(EMPTY_0)

    # Run Episode 0 Serially
    await producer_part_0()
    await consumer_part_0()
    
    # --- Episode 1: part_1 ---
    
    # Wait and clear empty_0 before entering buffer with second part
    empty_0_receipt = await robot.wait_event(EMPTY_0, TIMEOUT_S)
    robot.clear_event(EMPTY_0, expected_version=empty_0_receipt.version)
    
    # Producer (LEFT) for part_1
    async def producer_part_1():
        # Own tool
        await acquire_tool(LEFT)
        
        # Approach and Grasp part_1
        await robot.move(LEFT, SOURCE_1, timeout_s=TIMEOUT_S)
        await robot.grasp(LEFT, PART_1)
        
        # Own buffer_lock
        await acquire_buffer_lock(LEFT)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_1, timeout_s=TIMEOUT_S)
        
        # Release at buffer
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # Depart immediately
        await robot.move(LEFT, LEFT_WAIT, timeout_s=TIMEOUT_S)
        
        # Publish ready_1
        ready_1_receipt = robot.signal(READY_1, PART_1)
        
        # Release buffer_lock
        await release_buffer_lock(LEFT)
        
        # Release tool
        await release_tool(LEFT)
        
        return ready_1_receipt

    # Consumer (RIGHT) for part_1
    async def consumer_part_1():
        # Wait for ready_1
        ready_1_receipt = await robot.wait_event(READY_1, TIMEOUT_S)
        
        # Own buffer_lock
        await acquire_buffer_lock(RIGHT)
        
        # Approach and Grasp part_1
        await robot.move(RIGHT, BUFFER_1, timeout_s=TIMEOUT_S)
        await robot.grasp(RIGHT, PART_1)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_WAIT, timeout_s=TIMEOUT_S)
        
        # Release buffer_lock
        await release_buffer_lock(RIGHT)
        
        # Carried move to target_1 using ready_1_receipt
        await robot.move(RIGHT, TARGET_1, timeout_s=TIMEOUT_S, receipt=ready_1_receipt)
        
        # Clear ready_1 after carried move
        robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
        
        # Release at target
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # Depart to home
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # Publish empty_0 (final state requirement: events inactive, but signal then clear is standard, 
        # however goal says "events inactive". The consumer publishes empty_0. 
        # The goal "events inactive" implies they should be cleared or not active. 
        # Since empty_0 is signaled, we should clear it to satisfy "events inactive" if possible, 
        # or rely on the fact that we are done. 
        # The spec says "Consumer ... publishes empty_0". It does not explicitly say clear it.
        # However, for "events inactive", clearing is safer.
        # But wait, the goal says "events inactive". If I signal it, it is active.
        # I will clear it immediately to ensure inactivity.)
        # Actually, looking at the goal: "events inactive". 
        # I will signal it (as per "Consumer ... publishes empty_0") and then clear it.
        final_empty = robot.signal(EMPTY_0)
        robot.clear_event(EMPTY_0, expected_version=final_empty.version)

    # Run Episode 1 Serially (A alternates complete episodes)
    # Note: The prompt mentions "B runs producer and consumer coroutines together" for variant B.
    # This task is "SERIAL" (variant: "SERIAL", level: "SERIAL").
    # So we run them sequentially.
    
    # However, there is a specific requirement for item 1:
    # "For item 1, wait and clear empty_0, then inspect both readiness facts; C7 checks serially and C8 joins the two checks inside the loop branch."
    # This implies the inspection happens before the consumer starts or as part of it?
    # "Consumer waits the corresponding ready receipt before pickup".
    # The inspection of readiness facts seems to be a precondition or a check.
    # Since C8 joins the two checks, we do them concurrently.
    
    # Let's refine Episode 1 to include the inspections.
    
    async def producer_part_1_with_inspection():
        # Producer logic
        await acquire_tool(LEFT)
        await robot.move(LEFT, SOURCE_1, timeout_s=TIMEOUT_S)
        await robot.grasp(LEFT, PART_1)
        await acquire_buffer_lock(LEFT)
        await robot.move(LEFT, BUFFER_1, timeout_s=TIMEOUT_S)
        await robot.release(LEFT, PART_1, BUFFER_1)
        await robot.move(LEFT, LEFT_WAIT, timeout_s=TIMEOUT_S)
        ready_1_receipt = robot.signal(READY_1, PART_1)
        await release_buffer_lock(LEFT)
        await release_tool(LEFT)
        return ready_1_receipt

    async def consumer_part_1_with_inspection():
        # Wait for ready_1
        ready_1_receipt = await robot.wait_event(READY_1, TIMEOUT_S)
        
        # Inspections (Joined concurrency for C8)
        # "inspect both readiness facts"
        async def inspect_line_clear():
            await robot.inspect(RIGHT, FACT_LINE_CLEAR)
            
        async def inspect_receiver_ready():
            await robot.inspect(RIGHT, FACT_RECEIVER_READY)
            
        await asyncio.gather(inspect_line_clear(), inspect_receiver_ready())
        
        # Continue with consumer logic
        await acquire_buffer_lock(RIGHT)
        await robot.move(RIGHT, BUFFER_1, timeout_s=TIMEOUT_S)
        await robot.grasp(RIGHT, PART_1)
        await robot.move(RIGHT, RIGHT_WAIT, timeout_s=TIMEOUT_S)
        await release_buffer_lock(RIGHT)
        await robot.move(RIGHT, TARGET_1, timeout_s=TIMEOUT_S, receipt=ready_1_receipt)
        robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
        await robot.release(RIGHT, PART_1, TARGET_1)
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        final_empty = robot.signal(EMPTY_0)
        robot.clear_event(EMPTY_0, expected_version=final_empty.version)

    # Execute Episode 1
    await producer_part_1_with_inspection()
    await consumer_part_1_with_inspection()
    
    # Ensure LEFT is home (Producer ended at left_wait)
    await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_S)
