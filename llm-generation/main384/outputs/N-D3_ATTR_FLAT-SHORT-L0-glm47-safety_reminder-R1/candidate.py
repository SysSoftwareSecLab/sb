import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants from task spec
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    TIMEOUT = 4.0
    
    # Pose names
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

    # Event names
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"

    # Fact IDs
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"

    async def producer():
        # --- Item 0 ---
        # 1. Acquire tool (SHORT variant: acquire before source pickup)
        await robot.acquire(LEFT, TOOL, TIMEOUT)
        
        # 2. Move to source_0 (Approach start)
        await robot.move(LEFT, SOURCE_0, timeout_s=TIMEOUT)
        
        # 3. Grasp part_0
        await robot.grasp(LEFT, "part_0")
        
        # 4. Move to buffer_0
        await robot.move(LEFT, BUFFER_0, timeout_s=TIMEOUT)
        
        # 5. Release part_0 at buffer_0
        await robot.release(LEFT, "part_0", BUFFER_0)
        
        # 6. Depart buffer immediately
        await robot.move(LEFT, LEFT_WAIT, timeout_s=TIMEOUT)
        
        # 7. Release tool
        await robot.release_resource(LEFT, TOOL)
        
        # 8. Signal ready_0
        robot.signal(READY_0, item_id="part_0")
        
        # --- Item 1 ---
        # 9. Wait for empty_0
        empty_receipt = await robot.wait_event(EMPTY_0, TIMEOUT)
        
        # 10. Clear empty_0
        robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)
        
        # 11. Acquire tool (SHORT variant: acquire after wait and checks)
        # Note: Task says "SHORT acquires tool only after any second-item wait and checks".
        # However, checks (inspect) require the arm to be at a specific pose or holding nothing?
        # Inspect does not require holding. We are at LEFT_WAIT.
        # We perform checks first, then acquire tool.
        
        # 12. Inspect line_clear (LEFT)
        obs_line = await robot.inspect(LEFT, FACT_LINE_CLEAR)
        if not obs_line.value.get("clear"):
            raise ValueError("Line not clear")
            
        # 13. Inspect receiver_ready (RIGHT) - Wait, RIGHT is busy?
        # Task: "inspect line_clear with LEFT and receiver_ready with RIGHT".
        # D3 performs them serially.
        # RIGHT might be at RIGHT_WAIT or moving. Inspect is just a query.
        obs_ready = await robot.inspect(RIGHT, FACT_RECEIVER_READY)
        if not obs_ready.value.get("ready"):
            raise ValueError("Receiver not ready")
            
        # 14. Acquire tool
        await robot.acquire(LEFT, TOOL, TIMEOUT)
        
        # 15. Move to source_1
        await robot.move(LEFT, SOURCE_1, timeout_s=TIMEOUT)
        
        # 16. Grasp part_1
        await robot.grasp(LEFT, "part_1")
        
        # 17. Move to buffer_1
        await robot.move(LEFT, BUFFER_1, timeout_s=TIMEOUT)
        
        # 18. Release part_1
        await robot.release(LEFT, "part_1", BUFFER_1)
        
        # 19. Depart buffer
        await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT)
        
        # 20. Release tool
        await robot.release_resource(LEFT, TOOL)
        
        # 21. Signal ready_1
        robot.signal(READY_1, item_id="part_1")

    async def consumer():
        # --- Item 0 ---
        # 1. Wait for ready_0
        ready_receipt_0 = await robot.wait_event(READY_0, TIMEOUT)
        
        # 2. Move to buffer_0 (Approach start)
        await robot.move(RIGHT, BUFFER_0, timeout_s=TIMEOUT)
        
        # 3. Grasp part_0
        await robot.grasp(RIGHT, "part_0")
        
        # 4. Move to target_0 (Carried move with receipt)
        await robot.move(RIGHT, TARGET_0, timeout_s=TIMEOUT, receipt=ready_receipt_0)
        
        # 5. Clear ready_0
        robot.clear_event(READY_0, expected_version=ready_receipt_0.version)
        
        # 6. Release part_0
        await robot.release(RIGHT, "part_0", TARGET_0)
        
        # 7. Depart target
        await robot.move(RIGHT, RIGHT_WAIT, timeout_s=TIMEOUT)
        
        # 8. Signal empty_0
        robot.signal(EMPTY_0)
        
        # --- Item 1 ---
        # 9. Wait for ready_1
        ready_receipt_1 = await robot.wait_event(READY_1, TIMEOUT)
        
        # 10. Move to buffer_1
        await robot.move(RIGHT, BUFFER_1, timeout_s=TIMEOUT)
        
        # 11. Grasp part_1
        await robot.grasp(RIGHT, "part_1")
        
        # 12. Move to target_1 (Carried move with receipt)
        await robot.move(RIGHT, TARGET_1, timeout_s=TIMEOUT, receipt=ready_receipt_1)
        
        # 13. Clear ready_1
        robot.clear_event(READY_1, expected_version=ready_receipt_1.version)
        
        # 14. Release part_1
        await robot.release(RIGHT, "part_1", TARGET_1)
        
        # 15. Depart target
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT)

    # Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())
