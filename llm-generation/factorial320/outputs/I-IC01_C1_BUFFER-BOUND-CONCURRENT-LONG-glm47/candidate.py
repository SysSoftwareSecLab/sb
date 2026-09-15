import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
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
    GAP_0 = "rq2_gap_0"
    GAP_1 = "rq2_gap_1"
    GAP_2 = "rq2_gap_2"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    GATE = "rq2_gate"
    
    # Helper to acquire and release gaps in order
    async def manage_gaps():
        # Acquire in numeric order
        await robot.acquire(LEFT, GAP_0, 10.0)
        await robot.acquire(LEFT, GAP_1, 10.0)
        await robot.acquire(LEFT, GAP_2, 10.0)
        
        # Release in numeric order
        await robot.release_resource(LEFT, GAP_0)
        await robot.release_resource(LEFT, GAP_1)
        await robot.release_resource(LEFT, GAP_2)

    # Producer coroutine for a single part
    async def producer(part_id: str, source_pose: str, buffer_pose: str, ready_event: str):
        # Wait for empty_0 if not the first part (implied by sequence, but spec says wait and clear before entering buffer with second part)
        # For part_0, empty_0 is implicitly available (initial state).
        # For part_1, we must wait and clear empty_0.
        if part_id == PART_1:
            # Wait for empty_0 to be signaled
            empty_receipt = await robot.wait_event(EMPTY_0, 50.0)
            # Clear it
            robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)
            
        # Acquire buffer_lock
        await robot.acquire(LEFT, BUFFER_LOCK, 10.0)
        
        # Move to source (Approach)
        await robot.move(LEFT, source_pose)
        
        # Grasp part
        await robot.grasp(LEFT, part_id)
        
        # Move to buffer
        await robot.move(LEFT, buffer_pose)
        
        # Release part at buffer
        await robot.release(LEFT, part_id, buffer_pose)
        
        # Depart buffer immediately (Move to wait/home)
        # Spec: "Producer places each part at buffer and immediately departs before ready publication."
        # Using left_wait for part_1 to allow part_0 flow, or left_home.
        # Approach sequence for part_1 starts at left_wait.
        if part_id == PART_0:
            await robot.move(LEFT, LEFT_HOME)
        else:
            await robot.move(LEFT, LEFT_WAIT)
            
        # Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Publish ready event
        robot.signal(ready_event, item_id=part_id)

    # Consumer coroutine for a single part
    async def consumer(part_id: str, buffer_pose: str, target_pose: str, ready_event: str):
        # Wait for ready event
        ready_receipt = await robot.wait_event(ready_event, 50.0)
        
        # Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, 10.0)
        
        # Move to buffer (Approach)
        await robot.move(RIGHT, buffer_pose)
        
        # Grasp part
        await robot.grasp(RIGHT, part_id)
        
        # Depart buffer immediately
        # Spec: "Consumer waits the corresponding ready receipt before pickup, and supplies that exact active item receipt on carried move to target."
        # Spec: "Consumer clears ready after its carried move, releases on target and departs before publishing empty_0."
        # Move to target carrying the receipt
        await robot.move(RIGHT, target_pose, receipt=ready_receipt)
        
        # Clear ready event
        robot.clear_event(ready_event, expected_version=ready_receipt.version)
        
        # Release part at target
        await robot.release(RIGHT, part_id, target_pose)
        
        # Depart target (Move to wait/home)
        if part_id == PART_0:
            await robot.move(RIGHT, RIGHT_WAIT)
        else:
            await robot.move(RIGHT, RIGHT_HOME)
            
        # Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Publish empty_0
        # Spec: "Consumer ... departs before publishing empty_0."
        # Only consumer of part_0 needs to publish empty_0 to unblock producer of part_1?
        # Actually, producer of part_1 waits for empty_0. So consumer of part_0 must signal it.
        if part_id == PART_0:
            robot.signal(EMPTY_0)

    # --- RQ2_GATE Logic ---
    
    # 1. Signal rq2_gate
    gate_receipt = robot.signal(GATE)
    
    # 2. Complete all three rq2_gap resource checks (acquire/release)
    # Run concurrently with the dual-arm mission start
    gap_task = asyncio.create_task(manage_gaps())
    
    # 3. Wait for rq2_gate
    # Spec: "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    # This implies waiting for gaps to finish before waiting for gate?
    # Or "complete checks" means initiate them? "Acquire and release ... once each".
    # "complete all three ... and only then wait" suggests sequence: Signal -> (Do Gaps) -> Wait Gate.
    # However, "Keep rq2_gate active while executing the complete inherited dual-arm mission after the wait".
    # This implies the mission runs AFTER the wait.
    # So: Signal -> Gaps -> Wait Gate -> Mission.
    await gap_task
    
    # Wait for the gate we just signaled
    await robot.wait_event(GATE, 50.0)
    
    # --- Inherited Dual-Arm Mission ---
    
    # Run Producer and Consumer for Part 0
    prod0 = asyncio.create_task(producer(PART_0, SOURCE_0, BUFFER_0, READY_0))
    cons0 = asyncio.create_task(consumer(PART_0, BUFFER_0, TARGET_0, READY_0))
    
    # Wait for Part 0 to complete
    await prod0
    await cons0
    
    # Run Producer and Consumer for Part 1
    # Producer waits for empty_0 inside.
    prod1 = asyncio.create_task(producer(PART_1, SOURCE_1, BUFFER_1, READY_1))
    cons1 = asyncio.create_task(consumer(PART_1, BUFFER_1, TARGET_1, READY_1))
    
    # Wait for Part 1 to complete
    await prod1
    await cons1
    
    # --- Cleanup ---
    
    # Clear rq2_gate
    # Spec: "clear only after the mission"
    robot.clear_event(GATE, expected_version=gate_receipt.version)
    
    # Ensure arms are at home (Consumer of part 1 goes to right_home, Producer of part 1 goes to left_wait)
    # Need to move LEFT from left_wait to left_home
    await robot.move(LEFT, LEFT_HOME)
    
    # Events inactive: READY_0, READY_1, EMPTY_0 are cleared/consumed.
    # GATE is cleared.
    # Resources free: GAPs released, BUFFER_LOCK released.
