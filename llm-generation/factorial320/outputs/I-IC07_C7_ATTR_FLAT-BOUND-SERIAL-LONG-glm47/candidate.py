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
    
    # Items
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    # Resources
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    RQ2_GAP_0 = "rq2_gap_0"
    RQ2_GAP_1 = "rq2_gap_1"
    RQ2_GAP_2 = "rq2_gap_2"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    RQ2_GATE = "rq2_gate"
    
    # Facts
    LINE_CLEAR = "line_clear"
    RECEIVER_READY = "receiver_ready"

    # --- RQ2 Setup ---
    # Signal rq2_gate exactly once
    gate_receipt = robot.signal(RQ2_GATE)
    
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    await robot.acquire(LEFT, RQ2_GAP_0, 10.0)
    await robot.release_resource(LEFT, RQ2_GAP_0)
    
    await robot.acquire(LEFT, RQ2_GAP_1, 10.0)
    await robot.release_resource(LEFT, RQ2_GAP_1)
    
    await robot.acquire(LEFT, RQ2_GAP_2, 10.0)
    await robot.release_resource(LEFT, RQ2_GAP_2)
    
    # Wait for rq2_gate exactly once (after resource checks)
    await robot.wait_event(RQ2_GATE, 10.0)
    
    # --- Inherited Dual-Arm Mission (Serial Execution) ---
    
    # === Episode 0: part_0 ===
    
    # Producer (LEFT)
    # Acquire tool
    await robot.acquire(LEFT, TOOL, 10.0)
    
    # Move to source_0
    await robot.move(LEFT, SOURCE_0)
    
    # Grasp part_0
    obs_p0 = await robot.grasp(LEFT, PART_0)
    
    # Move to buffer_0
    await robot.acquire(LEFT, BUFFER_LOCK, 10.0)
    await robot.move(LEFT, BUFFER_0)
    
    # Release part_0 at buffer_0
    await robot.release(LEFT, PART_0, BUFFER_0)
    
    # Depart buffer (move to left_home)
    await robot.move(LEFT, LEFT_HOME)
    await robot.release_resource(LEFT, BUFFER_LOCK)
    
    # Publish ready_0
    ready_0_receipt = robot.signal(READY_0)
    
    # Consumer (RIGHT)
    # Wait for ready_0
    await robot.wait_event(READY_0, 10.0)
    
    # Move to buffer_0
    await robot.acquire(RIGHT, BUFFER_LOCK, 10.0)
    await robot.move(RIGHT, BUFFER_0)
    
    # Grasp part_0
    await robot.grasp(RIGHT, PART_0)
    
    # Move to target_0 with receipt
    await robot.move(RIGHT, TARGET_0, receipt=ready_0_receipt)
    
    # Clear ready_0
    robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
    
    # Release part_0 at target_0
    await robot.release(RIGHT, PART_0, TARGET_0)
    
    # Depart target (move to right_home)
    await robot.move(RIGHT, RIGHT_HOME)
    await robot.release_resource(RIGHT, BUFFER_LOCK)
    
    # Publish empty_0
    empty_0_receipt = robot.signal(EMPTY_0)
    
    # Release tool (Producer)
    await robot.release_resource(LEFT, TOOL)
    
    # === Episode 1: part_1 ===
    
    # Producer (LEFT)
    # Wait and clear empty_0
    await robot.wait_event(EMPTY_0, 10.0)
    robot.clear_event(EMPTY_0, expected_version=empty_0_receipt.version)
    
    # Inspect both readiness facts (C7 serially)
    await robot.inspect(LEFT, LINE_CLEAR)
    await robot.inspect(LEFT, RECEIVER_READY)
    
    # Acquire tool
    await robot.acquire(LEFT, TOOL, 10.0)
    
    # Move to source_1 (from left_wait per approach sequence)
    await robot.move(LEFT, LEFT_WAIT)
    await robot.move(LEFT, SOURCE_1)
    
    # Grasp part_1
    obs_p1 = await robot.grasp(LEFT, PART_1)
    
    # Move to buffer_1
    await robot.acquire(LEFT, BUFFER_LOCK, 10.0)
    await robot.move(LEFT, BUFFER_1)
    
    # Release part_1 at buffer_1
    await robot.release(LEFT, PART_1, BUFFER_1)
    
    # Depart buffer (move to left_home)
    await robot.move(LEFT, LEFT_HOME)
    await robot.release_resource(LEFT, BUFFER_LOCK)
    
    # Publish ready_1
    ready_1_receipt = robot.signal(READY_1)
    
    # Consumer (RIGHT)
    # Wait for ready_1
    await robot.wait_event(READY_1, 10.0)
    
    # Move to buffer_1 (from right_wait per approach sequence)
    await robot.move(RIGHT, RIGHT_WAIT)
    await robot.acquire(RIGHT, BUFFER_LOCK, 10.0)
    await robot.move(RIGHT, BUFFER_1)
    
    # Grasp part_1
    await robot.grasp(RIGHT, PART_1)
    
    # Move to target_1 with receipt
    await robot.move(RIGHT, TARGET_1, receipt=ready_1_receipt)
    
    # Clear ready_1
    robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
    
    # Release part_1 at target_1
    await robot.release(RIGHT, PART_1, TARGET_1)
    
    # Depart target (move to right_home)
    await robot.move(RIGHT, RIGHT_HOME)
    await robot.release_resource(RIGHT, BUFFER_LOCK)
    
    # Release tool (Producer)
    await robot.release_resource(LEFT, TOOL)
    
    # --- Cleanup ---
    # Clear rq2_gate exactly that version
    robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)
