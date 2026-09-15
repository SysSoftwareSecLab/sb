import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants derived from PUBLIC TASK
    ARMS = ["LEFT", "RIGHT"]
    PARTS = ["part_0", "part_1"]
    SOURCES = {"part_0": "source_0", "part_1": "source_1"}
    TARGETS = {"part_0": "target_0", "part_1": "target_1"}
    BUFFERS = {"part_0": "buffer_0", "part_1": "buffer_1"}
    READY_EVENTS = {"part_0": "ready_0", "part_1": "ready_1"}
    EMPTY_EVENT = "empty_0"
    LOCK_RESOURCE = "buffer_lock"
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_WAIT = "left_wait"
    RIGHT_HOME = "right_home"
    RIGHT_WAIT = "right_wait"

    # Durations
    TIMEOUT_MOVE = 4.0
    TIMEOUT_EVENT = 10.0

    async def producer(part_id: str):
        arm = "LEFT"
        source = SOURCES[part_id]
        buffer_pose = BUFFERS[part_id]
        ready_event = READY_EVENTS[part_id]
        
        # 1. Acquire lock
        await robot.acquire(arm, LOCK_RESOURCE, TIMEOUT_EVENT)
        
        # 2. Move to source and grasp
        # Approach sequence for part_0 starts at left_home, part_1 at left_wait
        start_pose = LEFT_HOME if part_id == "part_0" else LEFT_WAIT
        await robot.move(arm, start_pose, timeout_s=TIMEOUT_MOVE)
        await robot.move(arm, source, timeout_s=TIMEOUT_MOVE)
        await robot.grasp(arm, part_id)
        
        # 3. Move to buffer
        await robot.move(arm, buffer_pose, timeout_s=TIMEOUT_MOVE)
        
        # 4. Release at buffer
        await robot.release(arm, part_id, buffer_pose)
        
        # 5. Depart buffer (immediate separating departure)
        # Move to wait pose to clear buffer for consumer
        await robot.move(arm, LEFT_WAIT, timeout_s=TIMEOUT_MOVE)
        
        # 6. Release lock
        await robot.release_resource(arm, LOCK_RESOURCE)
        
        # 7. Signal ready
        robot.signal(ready_event)
        
        # 8. Return to home (optional but good for "empty arms at homes" goal)
        await robot.move(arm, LEFT_HOME, timeout_s=TIMEOUT_MOVE)

    async def consumer(part_id: str):
        arm = "RIGHT"
        buffer_pose = BUFFERS[part_id]
        target = TARGETS[part_id]
        ready_event = READY_EVENTS[part_id]
        
        # 1. Wait for ready event
        ready_receipt = await robot.wait_event(ready_event, TIMEOUT_EVENT)
        
        # 2. Acquire lock
        await robot.acquire(arm, LOCK_RESOURCE, TIMEOUT_EVENT)
        
        # 3. Move to buffer and grasp
        # Approach sequence for part_0 starts at right_home, part_1 at right_wait
        start_pose = RIGHT_HOME if part_id == "part_0" else RIGHT_WAIT
        await robot.move(arm, start_pose, timeout_s=TIMEOUT_MOVE)
        await robot.move(arm, buffer_pose, timeout_s=TIMEOUT_MOVE)
        await robot.grasp(arm, part_id)
        
        # 4. Depart buffer (immediate separating departure)
        await robot.move(arm, RIGHT_WAIT, timeout_s=TIMEOUT_MOVE)
        
        # 5. Release lock
        await robot.release_resource(arm, LOCK_RESOURCE)
        
        # 6. Move to target using receipt
        await robot.move(arm, target, timeout_s=TIMEOUT_MOVE, receipt=ready_receipt)
        
        # 7. Clear ready event
        robot.clear_event(ready_event, expected_version=ready_receipt.version)
        
        # 8. Release at target
        await robot.release(arm, part_id, target)
        
        # 9. Depart target
        await robot.move(arm, RIGHT_HOME, timeout_s=TIMEOUT_MOVE)
        
        # 10. Signal empty (only for part_0 as per "Consumer ... before publishing empty_0" and "Producer waits ... before entering buffer with the second part")
        if part_id == "part_0":
            robot.signal(EMPTY_EVENT)

    # Execution Strategy: B runs producer and consumer coroutines together.
    # We need to sequence the two parts (part_0 then part_1) because:
    # - Producer for part_1 waits for empty_0.
    # - Buffer is capacity-one.
    
    # Episode 1: part_0
    prod0 = asyncio.create_task(producer("part_0"))
    cons0 = asyncio.create_task(consumer("part_0"))
    await prod0
    await cons0
    
    # Episode 2: part_1
    # Producer for part_1 must wait for empty_0.
    # Consumer for part_1 can wait for ready_1.
    
    # Wait for empty_0 before starting producer for part_1
    empty_receipt = await robot.wait_event(EMPTY_EVENT, TIMEOUT_EVENT)
    robot.clear_event(EMPTY_EVENT, expected_version=empty_receipt.version)
    
    prod1 = asyncio.create_task(producer("part_1"))
    cons1 = asyncio.create_task(consumer("part_1"))
    await prod1
    await cons1
