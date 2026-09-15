import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants
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
    BUFFER_LOCK = "buffer_lock"
    TOOL = "tool"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"
    
    # Timeouts
    TIMEOUT_S = 50.0
    
    # Helper to check boolean fact value
    def check_fact_bool(obs: Observation, key: str) -> bool:
        return bool(obs.value.get(key, False))

    # --- Helper Coroutines for Episodes ---
    
    async def producer_episode(item_id: str, source_pose: str, buffer_pose: str, ready_event_id: str, wait_for_empty: bool = False):
        """
        Producer logic:
        1. Wait for empty_0 if required (for second item).
        2. Acquire buffer_lock.
        3. Move to source, grasp part.
        4. Move to buffer, release part.
        5. Depart buffer.
        6. Release buffer_lock.
        7. Signal ready event.
        """
        try:
            # 1. Wait for empty_0 if required
            if wait_for_empty:
                empty_receipt = await robot.wait_event(EMPTY_0, TIMEOUT_S)
                robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)
            
            # 2. Acquire buffer_lock
            await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
            
            # 3. Move to source and grasp
            await robot.move(LEFT, source_pose, timeout_s=TIMEOUT_S)
            await robot.grasp(LEFT, item_id)
            
            # 4. Move to buffer and release
            # LEFT owns tool during every buffer placement
            await robot.acquire(LEFT, TOOL, TIMEOUT_S)
            await robot.move(LEFT, buffer_pose, timeout_s=TIMEOUT_S)
            await robot.release(LEFT, item_id, buffer_pose)
            
            # 5. Depart buffer (Immediate departure)
            await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_S)
            
            # 6. Release buffer_lock
            await robot.release_resource(LEFT, BUFFER_LOCK)
            
            # 7. Signal ready
            robot.signal(ready_event_id, item_id=item_id)
            
        finally:
            # Release tool on every normal, failure and cancellation exit
            await robot.release_resource(LEFT, TOOL)

    async def consumer_episode(item_id: str, buffer_pose: str, target_pose: str, ready_event_id: str, is_second: bool = False):
        """
        Consumer logic:
        1. Wait for ready event.
        2. Acquire buffer_lock.
        3. Move to buffer, grasp part.
        4. Depart buffer.
        5. Release buffer_lock.
        6. Move to target (using receipt).
        7. Release part.
        8. Depart target.
        9. Clear ready.
        10. Signal empty_0.
        """
        try:
            # 1. Wait for ready event
            ready_receipt = await robot.wait_event(ready_event_id, TIMEOUT_S)
            
            # 2. Acquire buffer_lock
            await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
            
            # 3. Move to buffer and grasp
            await robot.move(RIGHT, buffer_pose, timeout_s=TIMEOUT_S)
            await robot.grasp(RIGHT, item_id)
            
            # 4. Depart buffer (Immediate departure)
            await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
            
            # 5. Release buffer_lock
            await robot.release_resource(RIGHT, BUFFER_LOCK)
            
            # 6. Move to target (using receipt)
            await robot.move(RIGHT, target_pose, timeout_s=TIMEOUT_S, receipt=ready_receipt)
            
            # 7. Release part
            await robot.release(RIGHT, item_id, target_pose)
            
            # 8. Depart target
            await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
            
            # 9. Clear ready
            robot.clear_event(ready_event_id, expected_version=ready_receipt.version)
            
            # 10. Signal empty_0
            robot.signal(EMPTY_0, item_id=item_id)
            
        finally:
            # Release tool on every normal, failure and cancellation exit
            await robot.release_resource(RIGHT, TOOL)

    async def second_item_checks():
        """
        For the second item, inspect line_clear with LEFT and receiver_ready with RIGHT.
        D3 performs the two second-item checks serially.
        """
        # Inspect line_clear with LEFT
        obs_line = await robot.inspect(LEFT, FACT_LINE_CLEAR)
        if not check_fact_bool(obs_line, "clear"):
            raise ValueError("line_clear check failed")
            
        # Inspect receiver_ready with RIGHT
        obs_recv = await robot.inspect(RIGHT, FACT_RECEIVER_READY)
        if not check_fact_bool(obs_recv, "ready"):
            raise ValueError("receiver_ready check failed")

    # --- Main Execution ---
    
    # Episode 1: part_0
    # Producer does not wait for empty_0. Consumer does not perform checks.
    # SHORT acquires tool only after any second-item wait and checks.
    # So for part 0, tool is acquired inside the episodes.
    
    prod_0 = asyncio.create_task(producer_episode(PART_0, SOURCE_0, BUFFER_0, READY_0, wait_for_empty=False))
    cons_0 = asyncio.create_task(consumer_episode(PART_0, BUFFER_0, TARGET_0, READY_0, is_second=False))
    
    await prod_0
    await cons_0
    
    # Episode 2: part_1
    # Producer waits for empty_0.
    # Consumer performs checks.
    # SHORT acquires tool only after any second-item wait and checks.
    
    # 1. Wait for empty_0 (Producer requirement)
    # Note: The producer coroutine handles the wait, but we need to ensure the checks happen
    # before the consumer acquires the tool and moves to target.
    # The consumer coroutine structure handles the tool acquisition.
    
    # We need to run the checks. The spec says "SHORT acquires tool only after any second-item wait and checks".
    # This implies the checks must happen before the tool is acquired for the transfer.
    # The consumer coroutine acquires the tool at the start of the try block.
    # To satisfy the constraint, we should perform checks *before* starting the consumer coroutine logic that acquires the tool.
    # However, the consumer also needs to wait for READY_1.
    # The spec says: "Consumer waits the corresponding ready receipt before pickup".
    # And "For the second item, after the exact empty_0 receipt is waited and cleared, inspect...".
    # This implies the checks happen after the producer signals empty_0 (from part 0) and before the consumer moves to target.
    # Since the consumer waits for READY_1, and READY_1 is signaled by the producer *after* the producer waits for empty_0,
    # the checks can be done after waiting for READY_1 but before acquiring the tool/moving to target.
    # But the consumer coroutine defined above acquires tool immediately.
    # Let's adjust the flow for the second item to be explicit about the order.
    
    # Step A: Producer waits for empty_0 and signals READY_1.
    # We can run the producer logic up to signaling READY_1.
    # But the producer also needs to place the part.
    # Let's run the producer task.
    
    prod_1 = asyncio.create_task(producer_episode(PART_1, SOURCE_1, BUFFER_1, READY_1, wait_for_empty=True))
    
    # Step B: Consumer waits for READY_1.
    ready_1_receipt = await robot.wait_event(READY_1, TIMEOUT_S)
    
    # Step C: Perform checks (D3 serial).
    await second_item_checks()
    
    # Step D: Consumer proceeds with pickup and transfer.
    # Now we acquire the tool (SHORT behavior).
    try:
        await robot.acquire(RIGHT, TOOL, TIMEOUT_S)
        
        # Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # Move to buffer and grasp
        await robot.move(RIGHT, BUFFER_1, timeout_s=TIMEOUT_S)
        await robot.grasp(RIGHT, PART_1)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Move to target with receipt
        await robot.move(RIGHT, TARGET_1, timeout_s=TIMEOUT_S, receipt=ready_1_receipt)
        
        # Release part
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # Clear ready
        robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
        
        # Signal empty_0
        robot.signal(EMPTY_0, item_id=PART_1)
        
    finally:
        await robot.release_resource(RIGHT, TOOL)
        
    # Wait for producer to finish (it should be done or almost done)
    await prod_1
