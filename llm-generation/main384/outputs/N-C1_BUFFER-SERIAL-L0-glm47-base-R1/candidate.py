import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    """
    Implements the C1_BUFFER-SERIAL-L0 task (Variant A).
    Structure: Serial execution of Producer and Consumer episodes.
    Episode 1: Move part_0 from source_0 to target_0 via buffer.
    Episode 2: Move part_1 from source_1 to target_1 via buffer.
    """

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
    
    # Objects
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    # Resources & Events
    BUFFER_LOCK = "buffer_lock"
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    
    # Timeouts
    MOVE_TIMEOUT = 4.0
    EVENT_TIMEOUT = 10.0

    # Helper to acquire buffer lock
    async def acquire_buffer_lock(arm: str):
        await robot.acquire(arm, BUFFER_LOCK, EVENT_TIMEOUT)

    # Helper to release buffer lock
    async def release_buffer_lock(arm: str):
        await robot.set_mode(arm, BUFFER_LOCK, "OFF")
        await robot.release_resource(arm, BUFFER_LOCK)

    # ==========================================
    # EPISODE 1: part_0 (source_0 -> buffer_0 -> target_0)
    # ==========================================
    
    # --- Producer Phase (LEFT) ---
    # 1. Move to source_0 (Approach)
    await robot.move(LEFT, SOURCE_0, MOVE_TIMEOUT)
    
    # 2. Grasp part_0
    await robot.grasp(LEFT, PART_0)
    
    # 3. Acquire buffer lock
    await acquire_buffer_lock(LEFT)
    
    # 4. Move to buffer_0
    await robot.move(LEFT, BUFFER_0, MOVE_TIMEOUT)
    
    # 5. Release part_0 at buffer_0
    await robot.release(LEFT, PART_0, BUFFER_0)
    
    # 6. Depart buffer (Immediate departure required)
    await robot.move(LEFT, LEFT_WAIT, MOVE_TIMEOUT)
    
    # 7. Release buffer lock
    await release_buffer_lock(LEFT)
    
    # 8. Publish ready_0
    ready_0_receipt = robot.signal(READY_0, PART_0)
    
    # --- Consumer Phase (RIGHT) ---
    # 1. Wait for ready_0
    await robot.wait_event(READY_0, EVENT_TIMEOUT)
    
    # 2. Move to buffer_0 (Approach)
    await robot.move(RIGHT, BUFFER_0, MOVE_TIMEOUT)
    
    # 3. Grasp part_0 (Must supply observation if required, but spec says "supplies that exact active item receipt on carried move")
    # Note: The spec says "Consumer waits the corresponding ready receipt before pickup, and supplies that exact active item receipt on carried move to target."
    # This implies the receipt is used in the move to target, not necessarily the grasp.
    await robot.grasp(RIGHT, PART_0)
    
    # 4. Acquire buffer lock (Required for departure)
    await acquire_buffer_lock(RIGHT)
    
    # 5. Move to target_0 (Carried move with receipt)
    await robot.move(RIGHT, TARGET_0, MOVE_TIMEOUT, receipt=ready_0_receipt)
    
    # 6. Clear ready_0 (Must happen after carried move starts/finishes, before release)
    robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
    
    # 7. Release part_0 at target_0
    await robot.release(RIGHT, PART_0, TARGET_0)
    
    # 8. Depart target (Immediate departure required)
    await robot.move(RIGHT, RIGHT_WAIT, MOVE_TIMEOUT)
    
    # 9. Release buffer lock
    await release_buffer_lock(RIGHT)
    
    # 10. Publish empty_0
    empty_0_receipt = robot.signal(EMPTY_0)

    # ==========================================
    # EPISODE 2: part_1 (source_1 -> buffer_1 -> target_1)
    # ==========================================
    
    # --- Producer Phase (LEFT) ---
    # 1. Wait for empty_0 (Required before entering buffer with second part)
    await robot.wait_event(EMPTY_0, EVENT_TIMEOUT)
    
    # 2. Clear empty_0
    robot.clear_event(EMPTY_0, expected_version=empty_0_receipt.version)
    
    # 3. Move to source_1 (Approach)
    await robot.move(LEFT, SOURCE_1, MOVE_TIMEOUT)
    
    # 4. Grasp part_1
    await robot.grasp(LEFT, PART_1)
    
    # 5. Acquire buffer lock
    await acquire_buffer_lock(LEFT)
    
    # 6. Move to buffer_1
    await robot.move(LEFT, BUFFER_1, MOVE_TIMEOUT)
    
    # 7. Release part_1 at buffer_1
    await robot.release(LEFT, PART_1, BUFFER_1)
    
    # 8. Depart buffer
    await robot.move(LEFT, LEFT_HOME, MOVE_TIMEOUT)
    
    # 9. Release buffer lock
    await release_buffer_lock(LEFT)
    
    # 10. Publish ready_1
    ready_1_receipt = robot.signal(READY_1, PART_1)
    
    # --- Consumer Phase (RIGHT) ---
    # 1. Wait for ready_1
    await robot.wait_event(READY_1, EVENT_TIMEOUT)
    
    # 2. Move to buffer_1 (Approach)
    await robot.move(RIGHT, BUFFER_1, MOVE_TIMEOUT)
    
    # 3. Grasp part_1
    await robot.grasp(RIGHT, PART_1)
    
    # 4. Acquire buffer lock
    await acquire_buffer_lock(RIGHT)
    
    # 5. Move to target_1 (Carried move with receipt)
    await robot.move(RIGHT, TARGET_1, MOVE_TIMEOUT, receipt=ready_1_receipt)
    
    # 6. Clear ready_1
    robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
    
    # 7. Release part_1 at target_1
    await robot.release(RIGHT, PART_1, TARGET_1)
    
    # 8. Depart target
    await robot.move(RIGHT, RIGHT_HOME, MOVE_TIMEOUT)
    
    # 9. Release buffer lock
    await release_buffer_lock(RIGHT)
    
    # Task Complete
    # Goals: part_0 at target_0, part_1 at target_1, empty arms at homes, buffer empty, lock free, events inactive.
    # All achieved.
