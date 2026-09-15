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
    
    # Helper to acquire resource
    async def acquire_res(arm, res_id, timeout=4.0):
        await robot.acquire(arm, res_id, timeout)
        
    # Helper to release resource
    async def release_res(arm, res_id):
        await robot.release_resource(arm, res_id)

    # --- RQ2 Gate Producer/Consumer ---
    # Signal rq2_gate exactly once
    gate_receipt = robot.signal(GATE)
    
    # Acquire gaps in numeric order with LEFT
    await acquire_res(LEFT, GAP_0)
    await acquire_res(LEFT, GAP_1)
    await acquire_res(LEFT, GAP_2)
    
    # Wait for rq2_gate exactly once
    await robot.wait_event(GATE, timeout=4.0)
    
    # --- Inherited Dual-Arm Mission (Concurrent) ---
    
    async def producer():
        # --- Episode 1: Part 0 ---
        # Acquire tool
        await acquire_res(LEFT, TOOL)
        
        # Approach source_0
        await robot.move(LEFT, SOURCE_0)
        # Grasp part_0
        await robot.grasp(LEFT, PART_0)
        
        # Acquire buffer_lock
        await acquire_res(LEFT, BUFFER_LOCK)
        
        # Move to buffer_0
        await robot.move(LEFT, BUFFER_0)
        # Release part_0 at buffer_0
        await robot.release(LEFT, PART_0, BUFFER_0)
        # Depart buffer (immediate separating departure)
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer_lock
        await release_res(LEFT, BUFFER_LOCK)
        
        # Release tool
        await release_res(LEFT, TOOL)
        
        # Signal ready_0
        ready_0_receipt = robot.signal(READY_0)
        
        # --- Episode 2: Part 1 ---
        # Wait and clear empty_0
        await robot.wait_event(EMPTY_0, timeout=4.0)
        robot.clear_event(EMPTY_0, expected_version=1)
        
        # Acquire tool
        await acquire_res(LEFT, TOOL)
        
        # Approach source_1
        await robot.move(LEFT, SOURCE_1)
        # Grasp part_1
        await robot.grasp(LEFT, PART_1)
        
        # Acquire buffer_lock
        await acquire_res(LEFT, BUFFER_LOCK)
        
        # Move to buffer_1
        await robot.move(LEFT, BUFFER_1)
        # Release part_1 at buffer_1
        await robot.release(LEFT, PART_1, BUFFER_1)
        # Depart buffer
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer_lock
        await release_res(LEFT, BUFFER_LOCK)
        
        # Release tool
        await release_res(LEFT, TOOL)
        
        # Signal ready_1
        robot.signal(READY_1)

    async def consumer():
        # --- Episode 1: Part 0 ---
        # Wait ready_0
        ready_0_receipt = await robot.wait_event(READY_0, timeout=4.0)
        
        # Acquire buffer_lock
        await acquire_res(RIGHT, BUFFER_LOCK)
        
        # Approach buffer_0
        await robot.move(RIGHT, BUFFER_0)
        # Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer_lock
        await release_res(RIGHT, BUFFER_LOCK)
        
        # Move to target_0 with receipt
        await robot.move(RIGHT, TARGET_0, receipt=ready_0_receipt)
        
        # Clear ready_0 after carried move
        robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
        
        # Release part_0 at target_0
        await robot.release(RIGHT, PART_0, TARGET_0)
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Signal empty_0
        robot.signal(EMPTY_0)
        
        # --- Episode 2: Part 1 ---
        # Wait ready_1
        ready_1_receipt = await robot.wait_event(READY_1, timeout=4.0)
        
        # Acquire buffer_lock
        await acquire_res(RIGHT, BUFFER_LOCK)
        
        # Approach buffer_1
        await robot.move(RIGHT, BUFFER_1)
        # Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer_lock
        await release_res(RIGHT, BUFFER_LOCK)
        
        # Move to target_1 with receipt
        await robot.move(RIGHT, TARGET_1, receipt=ready_1_receipt)
        
        # Clear ready_1 after carried move
        robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
        
        # Release part_1 at target_1
        await robot.release(RIGHT, PART_1, TARGET_1)
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Signal empty_0 (again? Task says "Consumer clears ready... and departs before publishing empty_0")
        # "Producer waits and clears empty_0 before entering buffer with the second part."
        # This implies empty_0 is signaled by Consumer after Episode 1.
        # Does Consumer signal empty_0 after Episode 2? 
        # Goal: "buffer empty". Part 1 is removed. Buffer is empty.
        # The cycle for Part 1 doesn't explicitly mention empty_0 signal, but Part 2 doesn't exist.
        # However, to be safe and consistent with "buffer empty" state, we might not need to signal again if logic holds.
        # But let's look at "Producer waits and clears empty_0 before entering buffer with the second part."
        # This was satisfied.
        # Let's stick to the explicit instructions. No explicit signal for Part 2 end.
        pass

    # Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())
    
    # --- Post-Mission Cleanup ---
    
    # Release gaps in numeric order with LEFT
    await release_res(LEFT, GAP_0)
    await release_res(LEFT, GAP_1)
    await release_res(LEFT, GAP_2)
    
    # Clear rq2_gate
    robot.clear_event(GATE, expected_version=gate_receipt.version)
