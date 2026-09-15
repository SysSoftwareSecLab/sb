import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
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
    TOOL = "tool"
    GAP_0 = "rq2_gap_0"
    GAP_1 = "rq2_gap_1"
    GAP_2 = "rq2_gap_2"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    GATE = "rq2_gate"

    # Helper to acquire resource
    async def acquire_res(arm: str, res: str):
        await robot.acquire(arm, res, 120.0)

    # Helper to release resource
    async def release_res(arm: str, res: str):
        await robot.set_mode(arm, res, "OFF")
        await robot.release_resource(arm, res)

    # --- RQ2 Gate Setup ---
    # Signal rq2_gate exactly once
    gate_receipt = robot.signal(GATE)
    
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    await acquire_res(LEFT, GAP_0)
    await release_res(LEFT, GAP_0)
    
    await acquire_res(LEFT, GAP_1)
    await release_res(LEFT, GAP_1)
    
    await acquire_res(LEFT, GAP_2)
    await release_res(LEFT, GAP_2)
    
    # Wait for rq2_gate exactly once (using the receipt we just signaled)
    # "wait its exact active receipt exactly once"
    await robot.wait_event(GATE, 120.0)
    
    # --- Inherited Dual-Arm Mission (Serial) ---
    # "Keep rq2_gate active while executing the complete inherited dual-arm mission"
    
    # === Episode 1: part_0 ===
    
    # Producer (LEFT)
    await robot.move(LEFT, LEFT_HOME)  # Ensure start
    await robot.move(LEFT, SOURCE_0)   # Approach
    await robot.grasp(LEFT, PART_0)    # Grasp
    
    await acquire_res(LEFT, TOOL)
    await acquire_res(LEFT, BUFFER_LOCK)
    
    await robot.move(LEFT, BUFFER_0)   # Place at buffer
    await robot.release(LEFT, PART_0, BUFFER_0)
    
    # Depart immediately before ready publication
    await robot.move(LEFT, LEFT_WAIT)
    await release_res(LEFT, BUFFER_LOCK)
    
    ready_0_receipt = robot.signal(READY_0)
    
    # Consumer (RIGHT)
    # Wait corresponding ready receipt
    await robot.wait_event(READY_0, 120.0)
    
    await robot.move(RIGHT, RIGHT_HOME)
    await robot.move(RIGHT, BUFFER_0)   # Approach
    await robot.grasp(RIGHT, PART_0)    # Grasp
    
    # Supplies that exact active item receipt on carried move to target
    await robot.move(RIGHT, TARGET_0, receipt=ready_0_receipt)
    
    # Consumer clears ready after its carried move
    robot.clear_event(READY_0, expected_version=ready_0_receipt.version)
    
    await robot.release(RIGHT, PART_0, TARGET_0)
    
    # Depart before publishing empty_0
    await robot.move(RIGHT, RIGHT_WAIT)
    empty_0_receipt = robot.signal(EMPTY_0)
    
    await release_res(LEFT, TOOL) # LEFT releases tool on every exit
    
    # === Episode 2: part_1 ===
    
    # Producer (LEFT)
    # Wait and clear empty_0 before entering buffer with the second part
    await robot.wait_event(EMPTY_0, 120.0)
    robot.clear_event(EMPTY_0, expected_version=empty_0_receipt.version)
    
    # For item 1, inspect both readiness facts
    # "C8 joins the two checks inside the loop branch" -> Serial execution
    obs_r0 = await robot.inspect(LEFT, "receiver_ready")
    obs_l0 = await robot.inspect(LEFT, "line_clear")
    
    await robot.move(LEFT, SOURCE_1)   # Approach
    await robot.grasp(LEFT, PART_1)    # Grasp
    
    await acquire_res(LEFT, TOOL)
    await acquire_res(LEFT, BUFFER_LOCK)
    
    await robot.move(LEFT, BUFFER_1)   # Place at buffer
    await robot.release(LEFT, PART_1, BUFFER_1)
    
    # Depart immediately
    await robot.move(LEFT, LEFT_WAIT)
    await release_res(LEFT, BUFFER_LOCK)
    
    ready_1_receipt = robot.signal(READY_1)
    
    # Consumer (RIGHT)
    await robot.wait_event(READY_1, 120.0)
    
    await robot.move(RIGHT, BUFFER_1)   # Approach
    await robot.grasp(RIGHT, PART_1)    # Grasp
    
    await robot.move(RIGHT, TARGET_1, receipt=ready_1_receipt)
    
    robot.clear_event(READY_1, expected_version=ready_1_receipt.version)
    
    await robot.release(RIGHT, PART_1, TARGET_1)
    await robot.move(RIGHT, RIGHT_HOME)
    
    await release_res(LEFT, TOOL)
    
    # --- Cleanup ---
    
    # Clear rq2_gate only after the mission
    robot.clear_event(GATE, expected_version=gate_receipt.version)
    
    # Ensure arms are at home (already done for RIGHT, LEFT is at WAIT)
    await robot.move(LEFT, LEFT_HOME)
