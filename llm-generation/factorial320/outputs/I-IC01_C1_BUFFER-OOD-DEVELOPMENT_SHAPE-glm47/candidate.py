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
    
    # Resources & Events
    BUFFER_LOCK = "buffer_lock"
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    RQ2_GATE = "rq2_gate"
    
    # Timeouts
    TIMEOUT_S = 4.0  # default_move_timeout_s
    
    # Helper to perform the Producer sequence for a specific part
    async def producer_part(part_id: str, source_pose: str, ready_event_id: str, wait_event_id: str):
        # 1. Wait for empty_0 (except for the very first part where it's implicitly available or logic handles it)
        # Task: "Producer waits and clears empty_0 before entering buffer with the second part."
        # For part_0, we assume buffer is empty initially.
        if part_id == PART_1:
            # Wait for empty_0 signal from consumer
            empty_receipt = await robot.wait_event(EMPTY_0, TIMEOUT_S)
            # Clear it
            robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)
        
        # 2. Acquire buffer_lock
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        
        # 3. Move to source (Approach)
        # Task: "Producer places each part at buffer and immediately departs before ready publication."
        # Approach sequence for LEFT/part_0 starts at left_home. For part_1 starts at left_wait.
        start_p = LEFT_HOME if part_id == PART_0 else LEFT_WAIT
        await robot.move(LEFT, start_p, TIMEOUT_S)
        await robot.move(LEFT, source_pose, TIMEOUT_S)
        
        # 4. Grasp
        await robot.grasp(LEFT, part_id)
        
        # 5. Move to buffer
        # buffer_0 and buffer_1 are identical coordinates.
        buffer_pose = BUFFER_0 if part_id == PART_0 else BUFFER_1
        await robot.move(LEFT, buffer_pose, TIMEOUT_S)
        
        # 6. Release at buffer
        await robot.release(LEFT, part_id, buffer_pose)
        
        # 7. Depart immediately
        # Task: "immediately departs before ready publication"
        # Move to wait pose to free up space
        await robot.move(LEFT, LEFT_WAIT, TIMEOUT_S)
        
        # 8. Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 9. Publish ready event
        ready_receipt = robot.signal(ready_event_id, item_id=part_id)
        
        # 10. Wait for rq2_gate (Consumer completion)
        # Task: "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
        # The producer waits for the gate to be signaled by the consumer.
        gate_receipt = await robot.wait_event(RQ2_GATE, TIMEOUT_S)
        robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)
        
        # 11. Clear ready event
        # Task: "consumer ... clears that version" (Wait, reading carefully)
        # "Consumer clears ready after its carried move... Producer waits and clears empty_0..."
        # The task says "Consumer clears ready after its carried move".
        # However, the "Inside one finite loop iteration... concurrently join... consumer itself has no mission guard"
        # implies the producer might need to clean up or the consumer does.
        # Let's re-read: "Consumer clears ready after its carried move... Producer waits and clears empty_0".
        # Okay, Consumer clears ready. Producer clears empty.
        # But wait, "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer; the consumer waits the exact active receipt, executes the complete inherited mission, then clears that version."
        # "clears that version" refers to the rq2_gate or the ready?
        # "Consumer clears ready after its carried move" is explicit in required_order.
        # So Producer does NOT clear ready.
        pass

    # Helper to perform the Consumer sequence for a specific part
    async def consumer_part(part_id: str, ready_event_id: str, target_pose: str, wait_pose: str):
        # 1. Wait for ready event
        ready_receipt = await robot.wait_event(ready_event_id, TIMEOUT_S)
        
        # 2. Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # 3. Move to buffer (Approach)
        # Approach sequence for RIGHT/part_0 starts at right_home. For part_1 starts at right_wait.
        start_p = RIGHT_HOME if part_id == PART_0 else RIGHT_WAIT
        await robot.move(RIGHT, start_p, TIMEOUT_S)
        await robot.move(RIGHT, BUFFER_0 if part_id == PART_0 else BUFFER_1, TIMEOUT_S)
        
        # 4. Grasp
        # Task: "Consumer waits the corresponding ready receipt before pickup, and supplies that exact active item receipt on carried move to target."
        # The grasp call signature is grasp(arm, object_id, *, observation=None).
        # The receipt is an EventReceipt. grasp takes Observation.
        # The API says: "grasp.observation: None or本控制器签发的Observation."
        # The task says "supplies that exact active item receipt on carried move to target".
        # This implies the receipt is passed to `move`, not `grasp`.
        # However, `move` signature is `move(arm, pose, timeout_s=None, *, receipt=None)`.
        # And `receipt` expects `EventReceipt`.
        # So we pass `ready_receipt` to the `move` that transports the part.
        # But we must grasp first.
        await robot.grasp(RIGHT, part_id)
        
        # 5. Move to target (Carried move)
        # "supplies that exact active item receipt on carried move to target"
        await robot.move(RIGHT, target_pose, TIMEOUT_S, receipt=ready_receipt)
        
        # 6. Clear ready event
        # Task: "Consumer clears ready after its carried move"
        robot.clear_event(ready_event_id, expected_version=ready_receipt.version)
        
        # 7. Release at target
        await robot.release(RIGHT, part_id, target_pose)
        
        # 8. Depart immediately
        # Task: "releases on target and departs before publishing empty_0"
        await robot.move(RIGHT, wait_pose, TIMEOUT_S)
        
        # 9. Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 10. Publish empty_0
        robot.signal(EMPTY_0)
        
        # 11. Signal rq2_gate
        # Task: "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
        # The consumer signals the gate to unblock the producer.
        robot.signal(RQ2_GATE)

    # Main Logic
    # Task: "A alternates complete producer/consumer episodes; B runs producer and consumer coroutines together."
    # Variant is A.
    # "Use the development shape FOR -> IF -> PAR_JOIN"
    # "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
    # This implies we run the producer and consumer for a part in parallel (joined), then loop for the next part.
    # Since there are two parts, we iterate twice.
    
    # Part 0
    # Producer for part 0 does not wait for empty_0 (assumed available).
    # Consumer for part 0 waits for ready_0.
    # They run concurrently.
    p0 = asyncio.create_task(producer_part(PART_0, SOURCE_0, READY_0, RQ2_GATE))
    c0 = asyncio.create_task(consumer_part(PART_0, READY_0, TARGET_0, RIGHT_WAIT))
    await asyncio.gather(p0, c0)
    
    # Part 1
    # Producer for part 1 waits for empty_0 (signaled by c0).
    # Consumer for part 1 waits for ready_1.
    # They run concurrently.
    p1 = asyncio.create_task(producer_part(PART_1, SOURCE_1, READY_1, RQ2_GATE))
    c1 = asyncio.create_task(consumer_part(PART_1, READY_1, TARGET_1, RIGHT_HOME))
    await asyncio.gather(p1, c1)
    
    # Final Goal: "empty arms at homes"
    # Part 0 Producer ended at LEFT_WAIT.
    # Part 1 Producer ended at LEFT_WAIT.
    # Part 0 Consumer ended at RIGHT_WAIT.
    # Part 1 Consumer ended at RIGHT_HOME.
    # We need to move LEFT to LEFT_HOME.
    await robot.move(LEFT, LEFT_HOME, TIMEOUT_S)
    
    # Task: "rq2_gate inactive at return"
    # The producer clears the gate after waiting.
    # The last producer (p1) cleared it.
    # So it should be inactive.
