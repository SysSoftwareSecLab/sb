import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot) -> None:
    # Constants
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
    BUFFER_LOCK = "buffer_lock"
    TOOL = "tool"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"
    
    # Helper to clear event
    def clear_event_sync(event_id: str, receipt: EventReceipt) -> None:
        robot.clear_event(event_id, expected_version=receipt.version)

    async def producer():
        # --- Part 0 ---
        # 1. Acquire buffer_lock
        await robot.acquire(LEFT, BUFFER_LOCK, timeout_s=4.0)
        
        # 2. Acquire tool (SHORT variant: acquire before buffer placement)
        await robot.acquire(LEFT, TOOL, timeout_s=4.0)
        
        # 3. Move to source_0
        await robot.move(LEFT, SOURCE_0, timeout_s=4.0)
        
        # 4. Grasp part_0
        await robot.grasp(LEFT, PART_0)
        
        # 5. Move to buffer_0
        await robot.move(LEFT, BUFFER_0, timeout_s=4.0)
        
        # 6. Release part_0 at buffer_0
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # 7. Depart buffer immediately
        await robot.move(LEFT, LEFT_HOME, timeout_s=4.0)
        
        # 8. Release tool
        await robot.release_resource(LEFT, TOOL)
        
        # 9. Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 10. Signal ready_0
        ready_0_receipt = robot.signal(READY_0, item_id=PART_0)
        
        # --- Part 1 ---
        # 11. Wait for empty_0
        empty_0_receipt = await robot.wait_event(EMPTY_0, timeout_s=50.0)
        
        # 12. Clear empty_0
        clear_event_sync(EMPTY_0, empty_0_receipt)
        
        # 13. Acquire buffer_lock
        await robot.acquire(LEFT, BUFFER_LOCK, timeout_s=4.0)
        
        # 14. Acquire tool
        await robot.acquire(LEFT, TOOL, timeout_s=4.0)
        
        # 15. Move to source_1
        await robot.move(LEFT, SOURCE_1, timeout_s=4.0)
        
        # 16. Grasp part_1
        await robot.grasp(LEFT, PART_1)
        
        # 17. Move to buffer_1
        await robot.move(LEFT, BUFFER_1, timeout_s=4.0)
        
        # 18. Release part_1 at buffer_1
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # 19. Depart buffer immediately
        await robot.move(LEFT, LEFT_HOME, timeout_s=4.0)
        
        # 20. Release tool
        await robot.release_resource(LEFT, TOOL)
        
        # 21. Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 22. Signal ready_1
        robot.signal(READY_1, item_id=PART_1)

    async def consumer():
        # --- Part 0 ---
        # 1. Wait for ready_0
        ready_0_receipt = await robot.wait_event(READY_0, timeout_s=50.0)
        
        # 2. Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, timeout_s=4.0)
        
        # 3. Move to buffer_0
        await robot.move(RIGHT, BUFFER_0, timeout_s=4.0)
        
        # 4. Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # 5. Depart buffer immediately
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=4.0)
        
        # 6. Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 7. Move to target_0 carrying part_0, using ready_0 receipt
        await robot.move(RIGHT, TARGET_0, timeout_s=4.0, receipt=ready_0_receipt)
        
        # 8. Clear ready_0
        clear_event_sync(READY_0, ready_0_receipt)
        
        # 9. Release part_0 at target_0
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # 10. Depart target immediately
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=4.0)
        
        # 11. Signal empty_0
        robot.signal(EMPTY_0)
        
        # --- Part 1 ---
        # 12. Wait for ready_1
        ready_1_receipt = await robot.wait_event(READY_1, timeout_s=50.0)
        
        # 13. Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, timeout_s=4.0)
        
        # 14. Move to buffer_1
        await robot.move(RIGHT, BUFFER_1, timeout_s=4.0)
        
        # 15. Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # 16. Depart buffer immediately
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=4.0)
        
        # 17. Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 18. Perform checks (SHORT variant: serially after wait and before transfer)
        # Check line_clear with LEFT
        obs_line = await robot.inspect(LEFT, FACT_LINE_CLEAR)
        if not obs_line.value.get("clear"):
            raise RuntimeError("line_clear check failed")
            
        # Check receiver_ready with RIGHT
        obs_recv = await robot.inspect(RIGHT, FACT_RECEIVER_READY)
        if not obs_recv.value.get("ready"):
            raise RuntimeError("receiver_ready check failed")
            
        # 19. Move to target_1 carrying part_1, using ready_1 receipt
        await robot.move(RIGHT, TARGET_1, timeout_s=4.0, receipt=ready_1_receipt)
        
        # 20. Clear ready_1
        clear_event_sync(READY_1, ready_1_receipt)
        
        # 21. Release part_1 at target_1
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # 22. Depart target immediately
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=4.0)

    # Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())
