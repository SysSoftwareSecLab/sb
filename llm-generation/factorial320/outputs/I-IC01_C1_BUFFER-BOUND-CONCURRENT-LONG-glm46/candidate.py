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
    
    # Timeouts
    TIMEOUT_S = 4.0
    
    # --- RQ2 Gate & Resource Checks (LEFT) ---
    # "Signal rq2_gate exactly once, wait its exact active receipt exactly once, and clear exactly that version after its assigned protected scope."
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order; never retain them at return."
    # "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    
    gate_receipt = robot.signal(GATE)
    
    await robot.acquire(LEFT, GAP_0, TIMEOUT_S)
    await robot.release_resource(LEFT, GAP_0)
    
    await robot.acquire(LEFT, GAP_1, TIMEOUT_S)
    await robot.release_resource(LEFT, GAP_1)
    
    await robot.acquire(LEFT, GAP_2, TIMEOUT_S)
    await robot.release_resource(LEFT, GAP_2)
    
    # Wait for the gate we just signaled
    active_gate_receipt = await robot.wait_event(GATE, TIMEOUT_S)
    
    # --- Concurrent Dual-Arm Mission ---
    # "Use joined concurrent scheduling for both the inherited dual-arm mission and the rq2_gate producer/consumer."
    # "Keep rq2_gate active while executing the complete inherited dual-arm mission after the wait; clear only after the mission."
    
    async def producer():
        # Episode 1: part_0
        # Move to source
        await robot.move(LEFT, SOURCE_0, TIMEOUT_S)
        # Grasp part_0
        grasp_obs_0 = await robot.grasp(LEFT, PART_0)
        
        # Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_0, TIMEOUT_S)
        # Release part_0 at buffer
        await robot.release(LEFT, PART_0, BUFFER_0)
        # Depart immediately
        await robot.move(LEFT, LEFT_HOME, TIMEOUT_S)
        
        # Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Signal ready_0
        ready_0_receipt = robot.signal(READY_0)
        
        # Wait for empty_0 before entering buffer with second part
        # "Producer waits and clears empty_0 before entering buffer with the second part."
        empty_0_receipt = await robot.wait_event(EMPTY_0, TIMEOUT_S)
        robot.clear_event(EMPTY_0, expected_version=empty_0_receipt.version)
        
        # Episode 2: part_1
        # Move to source_1 (start_pose left_wait)
        await robot.move(LEFT, SOURCE_1, TIMEOUT_S)
        # Grasp part_1
        grasp_obs_1 = await robot.grasp(LEFT, PART_1)
        
        # Acquire buffer lock
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_1, TIMEOUT_S)
        # Release part_1 at buffer
        await robot.release(LEFT, PART_1, BUFFER_1)
        # Depart immediately
        await robot.move(LEFT, LEFT_HOME, TIMEOUT_S)
        
        # Release buffer lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Signal ready_1
        robot.signal(READY_1)

    async def consumer():
        # Episode 1: part_0
        # Wait for ready_0
        ready_0_receipt = await robot.wait_event(READY_0, TIMEOUT_S)
        
        # Acquire buffer lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # Move to buffer
        await robot.move(RIGHT, BUFFER_0, TIMEOUT_S)
        # Grasp part_0
        grasp_obs_0 = await robot.grasp(RIGHT, PART_0)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_HOME, TIMEOUT_S)
        
        # Release buffer lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Move to target_0 using the ready receipt
        # "Consumer ... supplies that exact active item receipt on carried move to target."
        await robot.move(RIGHT, TARGET_0, TIMEOUT_S, receipt=ready_0_receipt)
        
        # Clear ready_0 after carried move
        # "Consumer clears ready after its carried move"
        robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
        
        # Release part_0 at target
        await robot.release(RIGHT, PART_0, TARGET_0)
        # Depart immediately
        await robot.move(RIGHT, RIGHT_HOME, TIMEOUT_S)
        
        # Signal empty_0
        # "Consumer ... departs before publishing empty_0."
        robot.signal(EMPTY_0)
        
        # Episode 2: part_1
        # Wait for ready_1
        ready_1_receipt = await robot.wait_event(READY_1, TIMEOUT_S)
        
        # Acquire buffer lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # Move to buffer
        await robot.move(RIGHT, BUFFER_1, TIMEOUT_S)
        # Grasp part_1
        grasp_obs_1 = await robot.grasp(RIGHT, PART_1)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_HOME, TIMEOUT_S)
        
        # Release buffer lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Move to target_1 using the ready receipt
        await robot.move(RIGHT, TARGET_1, TIMEOUT_S, receipt=ready_1_receipt)
        
        # Clear ready_1 after carried move
        robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
        
        # Release part_1 at target
        await robot.release(RIGHT, PART_1, TARGET_1)
        # Depart immediately
        await robot.move(RIGHT, RIGHT_HOME, TIMEOUT_S)

    # Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())
    
    # --- Cleanup ---
    # "clear only after the mission."
    robot.clear_event(GATE, expected_version=active_gate_receipt.version)
