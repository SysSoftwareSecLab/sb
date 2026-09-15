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
    
    # Items
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    # Resources
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    GAP_0 = "rq2_gap_0"
    GAP_1 = "rq2_gap_1"
    GAP_2 = "rq2_gap_2"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    GATE = "rq2_gate"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"
    
    # Timeout
    TIMEOUT = 50.0

    # --- RQ2 Gap Acquisition (LEFT) ---
    # Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order
    await robot.acquire(LEFT, GAP_0, TIMEOUT)
    await robot.release_resource(LEFT, GAP_0)
    
    await robot.acquire(LEFT, GAP_1, TIMEOUT)
    await robot.release_resource(LEFT, GAP_1)
    
    await robot.acquire(LEFT, GAP_2, TIMEOUT)
    await robot.release_resource(LEFT, GAP_2)
    
    # --- Signal RQ2 Gate ---
    # Signal rq2_gate exactly once
    gate_receipt = robot.signal(GATE)
    
    # --- Wait RQ2 Gate ---
    # Wait its exact active receipt exactly once
    # "wait immediately after the signal"
    await robot.wait_event(GATE, TIMEOUT)
    
    # --- Inherited Dual-Arm Mission (Concurrent) ---
    # "Use joined concurrent scheduling for both the inherited dual-arm mission"
    
    async def producer():
        # Episode 1: Part 0
        # Acquire tool
        await robot.acquire(LEFT, TOOL, TIMEOUT)
        
        # Move to source_0 (Approach start)
        await robot.move(LEFT, SOURCE_0)
        
        # Grasp part_0
        grasp_obs_0 = await robot.grasp(LEFT, PART_0)
        
        # Acquire buffer_lock for entry
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT)
        
        # Move to buffer_0
        await robot.move(LEFT, BUFFER_0)
        
        # Release part_0 at buffer_0
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # Depart buffer (immediate separating departure)
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer_lock after departure
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Signal ready_0
        ready_0_receipt = robot.signal(READY_0)
        
        # Release tool
        await robot.release_resource(LEFT, TOOL)
        
        # Episode 2: Part 1
        # Wait and clear empty_0 before entering buffer with the second part
        empty_0_wait = await robot.wait_event(EMPTY_0, TIMEOUT)
        robot.clear_event(EMPTY_0, expected_version=empty_0_wait.version)
        
        # Inspect both readiness facts
        # "For item 1, wait and clear empty_0, then inspect both readiness facts"
        obs_line = await robot.inspect(LEFT, FACT_LINE_CLEAR)
        obs_recv = await robot.inspect(LEFT, FACT_RECEIVER_READY)
        
        # Acquire tool
        await robot.acquire(LEFT, TOOL, TIMEOUT)
        
        # Move to source_1 (Approach start)
        await robot.move(LEFT, SOURCE_1)
        
        # Grasp part_1
        grasp_obs_1 = await robot.grasp(LEFT, PART_1)
        
        # Acquire buffer_lock for entry
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT)
        
        # Move to buffer_1
        await robot.move(LEFT, BUFFER_1)
        
        # Release part_1 at buffer_1
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # Depart buffer
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Signal ready_1
        ready_1_receipt = robot.signal(READY_1)
        
        # Release tool
        await robot.release_resource(LEFT, TOOL)

    async def consumer():
        # Episode 1: Part 0
        # Wait ready_0
        ready_0_wait = await robot.wait_event(READY_0, TIMEOUT)
        
        # Acquire buffer_lock for entry
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT)
        
        # Move to buffer_0 (Approach start)
        await robot.move(RIGHT, BUFFER_0)
        
        # Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Move to target_0 with receipt
        # "Consumer ... supplies that exact active item receipt on carried move to target"
        await robot.move(RIGHT, TARGET_0, receipt=ready_0_wait)
        
        # Clear ready_0 after carried move
        robot.clear_event(READY_0, expected_version=ready_0_wait.version)
        
        # Release part_0 at target_0
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Publish empty_0
        robot.signal(EMPTY_0)
        
        # Episode 2: Part 1
        # Wait ready_1
        ready_1_wait = await robot.wait_event(READY_1, TIMEOUT)
        
        # Acquire buffer_lock for entry
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT)
        
        # Move to buffer_1 (Approach start)
        await robot.move(RIGHT, BUFFER_1)
        
        # Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Move to target_1 with receipt
        await robot.move(RIGHT, TARGET_1, receipt=ready_1_wait)
        
        # Clear ready_1 after carried move
        robot.clear_event(READY_1, expected_version=ready_1_wait.version)
        
        # Release part_1 at target_1
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME)

    # Run concurrently
    await asyncio.gather(producer(), consumer())
    
    # --- Clear RQ2 Gate ---
    # "clear only after the mission"
    robot.clear_event(GATE, expected_version=gate_receipt.version)
