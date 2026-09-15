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
    
    # Timeout
    TIMEOUT = 10.0

    # --- RQ2 Gate Producer/Consumer ---
    # Signal rq2_gate exactly once
    gate_receipt = robot.signal(GATE)
    
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    await robot.acquire(LEFT, GAP_0, TIMEOUT)
    await robot.release_resource(LEFT, GAP_0)
    
    await robot.acquire(LEFT, GAP_1, TIMEOUT)
    await robot.release_resource(LEFT, GAP_1)
    
    await robot.acquire(LEFT, GAP_2, TIMEOUT)
    await robot.release_resource(LEFT, GAP_2)
    
    # Wait for rq2_gate exactly once (after resource checks)
    await robot.wait_event(GATE, TIMEOUT)
    
    # --- Inherited Dual-Arm Mission (Serial) ---
    # Part 0 Transfer
    
    # Producer (LEFT)
    await robot.move(LEFT, SOURCE_0)
    obs_p0 = await robot.grasp(LEFT, PART_0)
    
    await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT)
    await robot.move(LEFT, BUFFER_0)
    await robot.release(LEFT, PART_0, BUFFER_0)
    # Immediate departure
    await robot.move(LEFT, LEFT_HOME)
    await robot.release_resource(LEFT, BUFFER_LOCK)
    
    # Publish ready
    ready_0_receipt = robot.signal(READY_0)
    
    # Consumer (RIGHT)
    # Wait corresponding ready receipt
    await robot.wait_event(READY_0, TIMEOUT)
    
    # Pickup
    await robot.move(RIGHT, BUFFER_0)
    await robot.grasp(RIGHT, PART_0)
    
    # Acquire lock for departure
    await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT)
    
    # Carried move to target using receipt
    await robot.move(RIGHT, TARGET_0, receipt=ready_0_receipt)
    
    # Clear ready after carried move
    robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
    
    # Release on target
    await robot.release(RIGHT, PART_0, TARGET_0)
    # Depart
    await robot.move(RIGHT, RIGHT_HOME)
    await robot.release_resource(RIGHT, BUFFER_LOCK)
    
    # Publish empty
    empty_0_receipt = robot.signal(EMPTY_0)
    
    # Part 1 Transfer
    
    # Producer (LEFT)
    # Wait and clear empty_0
    await robot.wait_event(EMPTY_0, TIMEOUT)
    robot.clear_event(EMPTY_0, expected_version=empty_0_receipt.version)
    
    await robot.move(LEFT, SOURCE_1)
    obs_p1 = await robot.grasp(LEFT, PART_1)
    
    await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT)
    await robot.move(LEFT, BUFFER_1)
    await robot.release(LEFT, PART_1, BUFFER_1)
    # Immediate departure
    await robot.move(LEFT, LEFT_HOME)
    await robot.release_resource(LEFT, BUFFER_LOCK)
    
    # Publish ready
    ready_1_receipt = robot.signal(READY_1)
    
    # Consumer (RIGHT)
    # Wait corresponding ready receipt
    await robot.wait_event(READY_1, TIMEOUT)
    
    # Pickup
    await robot.move(RIGHT, BUFFER_1)
    await robot.grasp(RIGHT, PART_1)
    
    # Acquire lock for departure
    await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT)
    
    # Carried move to target using receipt
    await robot.move(RIGHT, TARGET_1, receipt=ready_1_receipt)
    
    # Clear ready after carried move
    robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
    
    # Release on target
    await robot.release(RIGHT, PART_1, TARGET_1)
    # Depart
    await robot.move(RIGHT, RIGHT_HOME)
    await robot.release_resource(RIGHT, BUFFER_LOCK)
    
    # --- Finalization ---
    # Clear rq2_gate exactly that version after its assigned protected scope
    robot.clear_event(GATE, expected_version=gate_receipt.version)
