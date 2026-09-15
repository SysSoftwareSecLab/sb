import asyncio
from bridge_robot_api import Robot, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants from task spec
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
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    RQ2_GATE = "rq2_gate"
    
    # Resources
    BUFFER_LOCK = "buffer_lock"
    
    # Durations
    TIMEOUT_S = 4.0
    
    # Helper to run producer logic for a specific part
    async def producer(part_id: str, source_pose: str, buffer_pose: str, ready_event: str, start_pose: str):
        # 1. Wait for empty_0 if not the first item (implied by "Producer waits and clears empty_0 before entering buffer with the second part")
        # For part_0, we assume empty_0 is implicitly available or we just proceed. 
        # The spec says "Producer waits and clears empty_0 before entering buffer with the second part."
        # We will handle the wait inside the loop logic or here.
        # Since this is a generic producer, we check if we need to wait.
        # However, the spec structure implies a sequence. 
        # Let's assume the caller handles the synchronization or we handle it here based on part_id.
        if part_id == PART_1:
            # Wait for empty_0 signal from consumer
            empty_receipt = await robot.wait_event(EMPTY_0, TIMEOUT_S)
            # Clear it
            robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)

        # 2. Acquire buffer_lock
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        
        # 3. Move to source (Approach)
        # Note: start_pose is left_home for part_0, left_wait for part_1
        await robot.move(LEFT, source_pose, TIMEOUT_S)
        
        # 4. Grasp
        await robot.grasp(LEFT, part_id)
        
        # 5. Move to buffer
        await robot.move(LEFT, buffer_pose, TIMEOUT_S)
        
        # 6. Release
        await robot.release(LEFT, part_id, buffer_pose)
        
        # 7. Depart immediately (Move to wait/home)
        # "Producer places each part at buffer and immediately departs before ready publication."
        # For part_0, depart to left_wait. For part_1, depart to left_home (goal).
        if part_id == PART_0:
            await robot.move(LEFT, LEFT_WAIT, TIMEOUT_S)
        else:
            await robot.move(LEFT, LEFT_HOME, TIMEOUT_S)
            
        # 8. Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 9. Signal ready
        robot.signal(ready_event, part_id)

    # Helper to run consumer logic for a specific part
    async def consumer(part_id: str, buffer_pose: str, target_pose: str, ready_event: str, start_pose: str):
        # 1. Wait for ready event
        ready_receipt = await robot.wait_event(ready_event, TIMEOUT_S)
        
        # 2. Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # 3. Move to buffer (Approach)
        await robot.move(RIGHT, buffer_pose, TIMEOUT_S)
        
        # 4. Grasp
        await robot.grasp(RIGHT, part_id)
        
        # 5. Depart buffer (Move to target)
        # "Consumer waits the corresponding ready receipt before pickup, and supplies that exact active item receipt on carried move to target."
        # The move to target carries the object.
        await robot.move(RIGHT, target_pose, TIMEOUT_S, receipt=ready_receipt)
        
        # 6. Clear ready event
        # "Consumer clears ready after its carried move"
        robot.clear_event(ready_event, expected_version=ready_receipt.version)
        
        # 7. Release
        await robot.release(RIGHT, part_id, target_pose)
        
        # 8. Depart immediately
        # "releases on target and departs before publishing empty_0"
        # For part_0, depart to right_wait. For part_1, depart to right_home (goal).
        if part_id == PART_0:
            await robot.move(RIGHT, RIGHT_WAIT, TIMEOUT_S)
        else:
            await robot.move(RIGHT, RIGHT_HOME, TIMEOUT_S)
            
        # 9. Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 10. Signal empty_0
        # "Consumer ... publishes empty_0"
        robot.signal(EMPTY_0)

    # Helper for RQ2_GATE producer
    async def rq2_producer():
        # Just signal the gate
        robot.signal(RQ2_GATE)

    # Helper for RQ2_GATE consumer
    async def rq2_consumer():
        # Wait for gate
        gate_receipt = await robot.wait_event(RQ2_GATE, TIMEOUT_S)
        # Clear it
        robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)

    # Main execution flow
    # "A alternates complete producer/consumer episodes"
    # Episode 1: part_0
    # Producer runs, then Consumer runs.
    
    # Producer for part_0
    await producer(PART_0, SOURCE_0, BUFFER_0, READY_0, LEFT_HOME)
    
    # Consumer for part_0
    await consumer(PART_0, BUFFER_0, TARGET_0, READY_0, RIGHT_HOME)
    
    # Episode 2: part_1
    # Producer for part_1 (waits for empty_0 inside)
    await producer(PART_1, SOURCE_1, BUFFER_1, READY_1, LEFT_WAIT)
    
    # Consumer for part_1
    await consumer(PART_1, BUFFER_1, TARGET_1, READY_1, RIGHT_WAIT)

    # RQ2_GATE Logic
    # "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
    # This seems to be a separate structural requirement or a final step.
    # Given the "A alternates" structure, we perform the RQ2_GATE step at the end.
    
    await asyncio.gather(
        rq2_producer(),
        rq2_consumer()
    )
