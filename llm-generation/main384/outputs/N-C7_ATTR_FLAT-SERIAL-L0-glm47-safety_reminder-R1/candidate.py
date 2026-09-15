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
    
    # Items
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    # Locations
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
    
    # Timeouts
    TIMEOUT_S = 4.0

    # Helper to clear event
    def clear_event_sync(event_id: str, receipt: EventReceipt):
        robot.clear_event(event_id, expected_version=receipt.version)

    # --- Episode 0: part_0 ---
    
    # 1. Producer (LEFT) moves to source_0, grasps part_0
    await robot.move(LEFT, SOURCE_0, timeout_s=TIMEOUT_S)
    await robot.grasp(LEFT, PART_0)
    
    # 2. Producer acquires tool and buffer_lock
    await robot.acquire(LEFT, TOOL, timeout_s=TIMEOUT_S)
    await robot.acquire(LEFT, BUFFER_LOCK, timeout_s=TIMEOUT_S)
    
    # 3. Producer moves to buffer_0, releases part_0
    await robot.move(LEFT, BUFFER_0, timeout_s=TIMEOUT_S)
    await robot.release(LEFT, PART_0, BUFFER_0)
    
    # 4. Producer departs buffer (move to left_wait) immediately
    await robot.move(LEFT, LEFT_WAIT, timeout_s=TIMEOUT_S)
    
    # 5. Producer releases buffer_lock
    await robot.release_resource(LEFT, BUFFER_LOCK)
    
    # 6. Producer signals ready_0
    ready_0_receipt = robot.signal(READY_0, item_id=PART_0)
    
    # 7. Consumer (RIGHT) waits for ready_0
    consumer_ready_0_receipt = await robot.wait_event(READY_0, timeout_s=TIMEOUT_S)
    
    # 8. Consumer moves to buffer_0, grasps part_0
    await robot.move(RIGHT, BUFFER_0, timeout_s=TIMEOUT_S)
    await robot.grasp(RIGHT, PART_0)
    
    # 9. Consumer departs buffer (move to right_wait) immediately
    await robot.move(RIGHT, RIGHT_WAIT, timeout_s=TIMEOUT_S)
    
    # 10. Consumer clears ready_0
    clear_event_sync(READY_0, consumer_ready_0_receipt)
    
    # 11. Consumer moves to target_0 using the ready receipt
    await robot.move(RIGHT, TARGET_0, timeout_s=TIMEOUT_S, receipt=consumer_ready_0_receipt)
    
    # 12. Consumer releases part_0 at target_0
    await robot.release(RIGHT, PART_0, TARGET_0)
    
    # 13. Consumer departs target (move to right_home) immediately
    await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
    
    # 14. Consumer signals empty_0
    robot.signal(EMPTY_0)
    
    # 15. Producer releases tool
    await robot.release_resource(LEFT, TOOL)

    # --- Episode 1: part_1 ---
    
    # 1. Producer waits and clears empty_0
    empty_0_receipt = await robot.wait_event(EMPTY_0, timeout_s=TIMEOUT_S)
    clear_event_sync(EMPTY_0, empty_0_receipt)
    
    # 2. Producer inspects both readiness facts (Serial check)
    obs_line_clear = await robot.inspect(LEFT, FACT_LINE_CLEAR)
    obs_receiver_ready = await robot.inspect(LEFT, FACT_RECEIVER_READY)
    
    # 3. Producer moves to source_1, grasps part_1
    await robot.move(LEFT, SOURCE_1, timeout_s=TIMEOUT_S)
    await robot.grasp(LEFT, PART_1)
    
    # 4. Producer acquires tool and buffer_lock
    await robot.acquire(LEFT, TOOL, timeout_s=TIMEOUT_S)
    await robot.acquire(LEFT, BUFFER_LOCK, timeout_s=TIMEOUT_S)
    
    # 5. Producer moves to buffer_1, releases part_1
    await robot.move(LEFT, BUFFER_1, timeout_s=TIMEOUT_S)
    await robot.release(LEFT, PART_1, BUFFER_1)
    
    # 6. Producer departs buffer (move to left_home) immediately
    await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_S)
    
    # 7. Producer releases buffer_lock
    await robot.release_resource(LEFT, BUFFER_LOCK)
    
    # 8. Producer signals ready_1
    ready_1_receipt = robot.signal(READY_1, item_id=PART_1)
    
    # 9. Consumer waits for ready_1
    consumer_ready_1_receipt = await robot.wait_event(READY_1, timeout_s=TIMEOUT_S)
    
    # 10. Consumer moves to buffer_1, grasps part_1
    await robot.move(RIGHT, BUFFER_1, timeout_s=TIMEOUT_S)
    await robot.grasp(RIGHT, PART_1)
    
    # 11. Consumer departs buffer (move to right_home) immediately
    await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
    
    # 12. Consumer clears ready_1
    clear_event_sync(READY_1, consumer_ready_1_receipt)
    
    # 13. Consumer moves to target_1 using the ready receipt
    await robot.move(RIGHT, TARGET_1, timeout_s=TIMEOUT_S, receipt=consumer_ready_1_receipt)
    
    # 14. Consumer releases part_1 at target_1
    await robot.release(RIGHT, PART_1, TARGET_1)
    
    # 15. Consumer departs target (move to right_home) immediately
    await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
    
    # 16. Producer releases tool
    await robot.release_resource(LEFT, TOOL)
