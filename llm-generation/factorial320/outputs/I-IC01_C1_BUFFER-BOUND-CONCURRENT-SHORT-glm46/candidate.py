import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

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
    
    # Objects
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    # Resources
    BUFFER_LOCK = "buffer_lock"
    RQ2_GAP_0 = "rq2_gap_0"
    RQ2_GAP_1 = "rq2_gap_1"
    RQ2_GAP_2 = "rq2_gap_2"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    RQ2_GATE = "rq2_gate"
    
    # Timeouts
    TIMEOUT_S = 4.0
    
    # --- RQ2 Gap Resource Checks (LEFT arm, numeric order) ---
    # Must be done before signalling rq2_gate
    await robot.acquire(LEFT, RQ2_GAP_0, TIMEOUT_S)
    await robot.release_resource(LEFT, RQ2_GAP_0)
    
    await robot.acquire(LEFT, RQ2_GAP_1, TIMEOUT_S)
    await robot.release_resource(LEFT, RQ2_GAP_1)
    
    await robot.acquire(LEFT, RQ2_GAP_2, TIMEOUT_S)
    await robot.release_resource(LEFT, RQ2_GAP_2)
    
    # --- Signal RQ2_GATE ---
    # Signal exactly once
    gate_receipt = robot.signal(RQ2_GATE)
    
    # Wait immediately after signal
    # Wait its exact active receipt exactly once
    await robot.wait_event(RQ2_GATE, TIMEOUT_S)
    
    # --- Inherited Dual-Arm Mission (Concurrent) ---
    # Structure: Producer (LEFT) moves part to buffer, Consumer (RIGHT) moves to target.
    # Variant B: Run producer and consumer coroutines together.
    
    async def producer_part_0():
        # 1. Wait and clear empty_0 before entering buffer
        await robot.wait_event(EMPTY_0, TIMEOUT_S)
        robot.clear_event(EMPTY_0, expected_version=1)
        
        # 2. Acquire buffer_lock
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        
        # 3. Approach and Grasp part_0
        # Approach sequence: start_pose=left_home, interaction_pose=source_0, required_next=grasp
        await robot.move(LEFT, SOURCE_0, timeout_s=TIMEOUT_S)
        obs_0 = await robot.grasp(LEFT, PART_0)
        
        # 4. Move to buffer
        await robot.move(LEFT, BUFFER_0, timeout_s=TIMEOUT_S)
        
        # 5. Release at buffer
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # 6. Depart immediately (release starts departure)
        await robot.move(LEFT, LEFT_WAIT, timeout_s=TIMEOUT_S)
        
        # 7. Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 8. Publish ready_0
        robot.signal(READY_0)
        
    async def consumer_part_0():
        # 1. Wait ready_0
        ready_0_receipt = await robot.wait_event(READY_0, TIMEOUT_S)
        
        # 2. Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # 3. Approach and Grasp part_0
        # Approach sequence: start_pose=right_home, interaction_pose=buffer_0, required_next=grasp
        await robot.move(RIGHT, BUFFER_0, timeout_s=TIMEOUT_S)
        obs_0 = await robot.grasp(RIGHT, PART_0)
        
        # 4. Move to target with receipt
        # Consumer supplies that exact active item receipt on carried move to target
        await robot.move(RIGHT, TARGET_0, timeout_s=TIMEOUT_S, receipt=ready_0_receipt)
        
        # 5. Clear ready after carried move
        robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
        
        # 6. Release at target
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # 7. Depart immediately
        await robot.move(RIGHT, RIGHT_WAIT, timeout_s=TIMEOUT_S)
        
        # 8. Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 9. Publish empty_0
        robot.signal(EMPTY_0)
        
    async def producer_part_1():
        # 1. Wait and clear empty_0 before entering buffer with second part
        await robot.wait_event(EMPTY_0, TIMEOUT_S)
        robot.clear_event(EMPTY_0, expected_version=2)
        
        # 2. Acquire buffer_lock
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        
        # 3. Approach and Grasp part_1
        # Approach sequence: start_pose=left_wait, interaction_pose=source_1, required_next=grasp
        await robot.move(LEFT, SOURCE_1, timeout_s=TIMEOUT_S)
        obs_1 = await robot.grasp(LEFT, PART_1)
        
        # 4. Move to buffer
        await robot.move(LEFT, BUFFER_1, timeout_s=TIMEOUT_S)
        
        # 5. Release at buffer
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # 6. Depart immediately
        await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_S)
        
        # 7. Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # 8. Publish ready_1
        robot.signal(READY_1)
        
    async def consumer_part_1():
        # 1. Wait ready_1
        ready_1_receipt = await robot.wait_event(READY_1, TIMEOUT_S)
        
        # 2. Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # 3. Approach and Grasp part_1
        # Approach sequence: start_pose=right_wait, interaction_pose=buffer_1, required_next=grasp
        await robot.move(RIGHT, BUFFER_1, timeout_s=TIMEOUT_S)
        obs_1 = await robot.grasp(RIGHT, PART_1)
        
        # 4. Move to target with receipt
        await robot.move(RIGHT, TARGET_1, timeout_s=TIMEOUT_S, receipt=ready_1_receipt)
        
        # 5. Clear ready after carried move
        robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
        
        # 6. Release at target
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # 7. Depart immediately
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # 8. Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # 9. Publish empty_0 (Final state requires empty_0 active? No, "events inactive" in goal, but consumer publishes empty_0)
        # Goal: "events inactive". So we should not signal empty_0 here if we want them inactive at return.
        # However, "Consumer ... before publishing empty_0" implies the action.
        # But goal says "events inactive". 
        # Let's check the goal again: "part_0 at target_0; part_1 at target_1; empty arms at homes; buffer empty; lock free; events inactive".
        # If we signal empty_0, it becomes active.
        # The instruction "Consumer ... before publishing empty_0" describes the protocol flow.
        # If the goal requires inactive events, we must clear them or not signal them.
        # Given "events inactive" is a hard goal, and "empty_0" is the only event that might be signaled at the end,
        # we should probably NOT signal it, or signal and clear it immediately?
        # The protocol says "Consumer ... before publishing empty_0". This implies the signal happens.
        # But the goal says "events inactive".
        # Let's look at the Producer Part 0: "wait and clear empty_0". This implies empty_0 was active.
        # If we don't signal it at the end of Consumer Part 1, Producer Part 0 (if it looped) would hang.
        # Since this is a finite task, maybe we just don't signal it?
        # Or maybe we signal it and the environment clears it? No, "program_clearable".
        # Let's assume the goal overrides the protocol description for the final step, or we clear it.
        # Actually, if we don't signal it, the "buffer empty" state is achieved, but the event isn't signaled.
        # Let's stick to the goal "events inactive". I will NOT signal empty_0 at the end.
        pass

    # Schedule
    # Part 0: Producer waits for empty_0 (init version 0, signaled? No. initial_version 0. Wait waits for active. 
    # Wait, if initial_version is 0, is it active? Usually version 0 means not signaled yet.
    # But Producer Part 0 waits for empty_0. If it's not signaled, it waits forever.
    # Maybe the environment signals it? Or maybe I should signal it?
    # "Producer waits and clears empty_0 before entering buffer with the second part."
    # This applies to Part 1.
    # For Part 0, the buffer is initially empty. Does it need to wait for empty_0?
    # "Producer places each part at buffer... Consumer ... before publishing empty_0."
    # This implies a cycle: empty_0 -> Producer -> ready_0 -> Consumer -> empty_0.
    # So for Part 0, empty_0 must be active initially?
    # Or maybe the "wait" is only for Part 1?
    # "Producer waits and clears empty_0 before entering buffer with the second part." -> Explicit for Part 1.
    # What about Part 0? "Producer places each part at buffer...".
    # If I don't wait for empty_0 for Part 0, I can start immediately.
    # But if I don't wait, and Consumer Part 1 publishes empty_0, then Producer Part 1 waits.
    # This makes sense.
    # So Producer Part 0 does NOT wait for empty_0.
    
    # Revised Producer Part 0
    async def prod_0():
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        await robot.move(LEFT, SOURCE_0, timeout_s=TIMEOUT_S)
        await robot.grasp(LEFT, PART_0)
        await robot.move(LEFT, BUFFER_0, timeout_s=TIMEOUT_S)
        await robot.release(LEFT, PART_0, BUFFER_0)
        await robot.move(LEFT, LEFT_WAIT, timeout_s=TIMEOUT_S)
        await robot.release_resource(LEFT, BUFFER_LOCK)
        robot.signal(READY_0)

    # Revised Producer Part 1
    async def prod_1():
        # Wait and clear empty_0
        await robot.wait_event(EMPTY_0, TIMEOUT_S)
        # Who signals empty_0? Consumer Part 0.
        # So Consumer Part 0 must signal it.
        # But Goal says "events inactive".
        # If Consumer Part 0 signals it, it becomes active.
        # If Producer Part 1 clears it, it becomes inactive.
        # This works for the cycle.
        # What about the end? Consumer Part 1 finishes.
        # If Consumer Part 1 signals empty_0, it is active. Goal fails.
        # So Consumer Part 1 should NOT signal empty_0.
        # This breaks the cycle if there were a Part 2, but there isn't.
        
        robot.clear_event(EMPTY_0, expected_version=1)
        
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        await robot.move(LEFT, SOURCE_1, timeout_s=TIMEOUT_S)
        await robot.grasp(LEFT, PART_1)
        await robot.move(LEFT, BUFFER_1, timeout_s=TIMEOUT_S)
        await robot.release(LEFT, PART_1, BUFFER_1)
        await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_S)
        await robot.release_resource(LEFT, BUFFER_LOCK)
        robot.signal(READY_1)

    # Revised Consumer Part 0
    async def cons_0():
        r0 = await robot.wait_event(READY_0, TIMEOUT_S)
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        await robot.move(RIGHT, BUFFER_0, timeout_s=TIMEOUT_S)
        await robot.grasp(RIGHT, PART_0)
        await robot.move(RIGHT, TARGET_0, timeout_s=TIMEOUT_S, receipt=r0)
        robot.clear_event(READY_0, expected_version=r0.version)
        await robot.release(RIGHT, PART_0, TARGET_0)
        await robot.move(RIGHT, RIGHT_WAIT, timeout_s=TIMEOUT_S)
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        # Signal empty_0 for Part 1
        robot.signal(EMPTY_0)

    # Revised Consumer Part 1
    async def cons_1():
        r1 = await robot.wait_event(READY_1, TIMEOUT_S)
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        await robot.move(RIGHT, BUFFER_1, timeout_s=TIMEOUT_S)
        await robot.grasp(RIGHT, PART_1)
        await robot.move(RIGHT, TARGET_1, timeout_s=TIMEOUT_S, receipt=r1)
        robot.clear_event(READY_1, expected_version=r1.version)
        await robot.release(RIGHT, PART_1, TARGET_1)
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        # Do NOT signal empty_0 to satisfy "events inactive"

    # Execution
    # Part 0 Producer and Consumer run concurrently.
    await asyncio.gather(prod_0(), cons_0())
    
    # Part 1 Producer and Consumer run concurrently.
    await asyncio.gather(prod_1(), cons_1())
    
    # --- Clear RQ2_GATE ---
    # Clear exactly that version after its assigned protected scope.
    # Scope was the inherited dual-arm mission.
    robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)
