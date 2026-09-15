import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
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
    
    # Resources & Events
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"

    async def producer(item_id: str, source_pose: str, buffer_pose: str, ready_event: str, wait_pose: str):
        # 1. Acquire tool
        await robot.acquire(LEFT, TOOL, 4.0)
        
        # 2. Move to source and grasp
        await robot.move(LEFT, source_pose)
        obs = await robot.grasp(LEFT, item_id)
        
        # 3. Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, 4.0)
        
        # 4. Move to buffer
        await robot.move(LEFT, buffer_pose)
        
        # 5. Release at buffer
        await robot.release(LEFT, item_id, buffer_pose)
        
        # 6. Depart buffer (immediate separation)
        await robot.move(LEFT, wait_pose)
        
        # 7. Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 8. Release tool
        await robot.release_resource(LEFT, TOOL)
        
        # 9. Signal ready
        receipt = robot.signal(ready_event, item_id)
        
        return receipt

    async def consumer(item_id: str, buffer_pose: str, target_pose: str, ready_event: str, wait_pose: str, is_second: bool):
        # 1. Wait for ready event
        ready_receipt = await robot.wait_event(ready_event, 50.0)
        
        # 2. Acquire buffer lock
        await robot.acquire(RIGHT, BUFFER_LOCK, 4.0)
        
        # 3. Move to buffer and grasp
        await robot.move(RIGHT, buffer_pose)
        await robot.grasp(RIGHT, item_id)
        
        # 4. Depart buffer (immediate separation)
        await robot.move(RIGHT, wait_pose)
        
        # 5. Release buffer lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 6. Move to target using receipt
        await robot.move(RIGHT, target_pose, receipt=ready_receipt)
        
        # 7. Clear ready event
        robot.clear_event(ready_event, expected_version=ready_receipt.version)
        
        # 8. Release at target
        await robot.release(RIGHT, item_id, target_pose)
        
        # 9. Depart target
        await robot.move(RIGHT, RIGHT_HOME)
        
        # 10. Signal empty
        robot.signal(EMPTY_0)

    # Run Part 0 (Producer and Consumer concurrently)
    prod_0 = asyncio.create_task(producer(PART_0, SOURCE_0, BUFFER_0, READY_0, LEFT_WAIT))
    cons_0 = asyncio.create_task(consumer(PART_0, BUFFER_0, TARGET_0, READY_0, RIGHT_WAIT, False))
    
    await prod_0
    await cons_0
    
    # Run Part 1 (Producer and Consumer concurrently)
    # Producer waits for empty_0 before entering buffer logic
    prod_1 = asyncio.create_task(producer(PART_1, SOURCE_1, BUFFER_1, READY_1, LEFT_WAIT))
    cons_1 = asyncio.create_task(consumer(PART_1, BUFFER_1, TARGET_1, READY_1, RIGHT_WAIT, True))
    
    # Wait for empty_0 before starting producer logic for part 1
    empty_receipt = await robot.wait_event(EMPTY_0, 50.0)
    robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)
    
    # Inspect facts for Part 1
    await robot.inspect(RIGHT, FACT_LINE_CLEAR)
    await robot.inspect(RIGHT, FACT_RECEIVER_READY)
    
    await prod_1
    await cons_1
