import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
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
    
    # Items
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"
    
    # Helper to check boolean fields in observation value
    def check_bool_fact(obs: Observation, field: str) -> bool:
        return obs.value.get(field, False)

    async def producer():
        # LONG variant: Acquire tool before source pickup
        await robot.acquire(LEFT, TOOL, timeout_s=4.0)
        
        # --- Episode 1: part_0 ---
        # Move to source
        await robot.move(LEFT, SOURCE_0)
        # Grasp part_0
        await robot.grasp(LEFT, PART_0)
        
        # Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, timeout_s=4.0)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_0)
        # Release part_0
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # Depart buffer immediately
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Signal ready_0
        ready_0_receipt = robot.signal(READY_0, item_id=PART_0)
        
        # --- Episode 2: part_1 ---
        # Wait for empty_0
        empty_0_receipt = await robot.wait_event(EMPTY_0, timeout_s=50.0)
        
        # Clear empty_0
        robot.clear_event(EMPTY_0, expected_version=empty_0_receipt.version)
        
        # Move to source_1
        await robot.move(LEFT, SOURCE_1)
        # Grasp part_1
        await robot.grasp(LEFT, PART_1)
        
        # Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, timeout_s=4.0)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_1)
        # Release part_1
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # Depart buffer immediately
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Signal ready_1
        robot.signal(READY_1, item_id=PART_1)
        
        # Release tool
        await robot.release_resource(LEFT, TOOL)

    async def consumer():
        # --- Episode 1: part_0 ---
        # Wait for ready_0
        ready_0_receipt = await robot.wait_event(READY_0, timeout_s=50.0)
        
        # Acquire buffer lock
        await robot.acquire(RIGHT, BUFFER_LOCK, timeout_s=4.0)
        
        # Move to buffer
        await robot.move(RIGHT, BUFFER_0)
        # Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # Depart buffer immediately
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Move to target with receipt
        await robot.move(RIGHT, TARGET_0, receipt=ready_0_receipt)
        
        # Clear ready_0
        robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
        
        # Release part_0
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # Depart target immediately
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Signal empty_0
        robot.signal(EMPTY_0)
        
        # --- Episode 2: part_1 ---
        # Wait for ready_1
        ready_1_receipt = await robot.wait_event(READY_1, timeout_s=50.0)
        
        # Acquire buffer lock
        await robot.acquire(RIGHT, BUFFER_LOCK, timeout_s=4.0)
        
        # Move to buffer
        await robot.move(RIGHT, BUFFER_1)
        # Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # Depart buffer immediately
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # D4: Join checks with asyncio.gather
        # "For the second item, after the exact empty_0 receipt is waited and cleared, 
        # inspect line_clear with LEFT and receiver_ready with RIGHT"
        # Note: empty_0 receipt was waited and cleared in producer. 
        # The consumer waits ready_1. The checks happen before transfer to target.
        
        # We need to inspect facts. LEFT must inspect line_clear, RIGHT must inspect receiver_ready.
        # Since consumer controls RIGHT, and LEFT is idle (producer finished or waiting), 
        # we can run these in parallel.
        
        # However, the prompt says "inspect line_clear with LEFT". 
        # The consumer coroutine is the one performing the transfer logic.
        # It can issue commands to LEFT.
        
        check_left = robot.inspect(LEFT, FACT_LINE_CLEAR)
        check_right = robot.inspect(RIGHT, FACT_RECEIVER_READY)
        
        obs_left, obs_right = await asyncio.gather(check_left, check_right)
        
        # Verify fields (internal verification)
        assert check_bool_fact(obs_left, "clear"), "line_clear check failed"
        assert check_bool_fact(obs_right, "ready"), "receiver_ready check failed"
        
        # Move to target with receipt
        await robot.move(RIGHT, TARGET_1, receipt=ready_1_receipt)
        
        # Clear ready_1
        robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
        
        # Release part_1
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # Depart target immediately
        await robot.move(RIGHT, RIGHT_HOME)

    # Run producer and consumer together
    await asyncio.gather(producer(), consumer())
