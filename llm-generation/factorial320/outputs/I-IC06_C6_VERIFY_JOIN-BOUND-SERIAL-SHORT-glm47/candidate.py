import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_SOURCE = "left_source"
    LEFT_TARGET = "left_target"
    LEFT_DEPART = "left_depart"
    
    RIGHT_HOME = "right_home"
    RIGHT_SOURCE = "right_source"
    RIGHT_TARGET = "right_target"
    RIGHT_DEPART = "right_depart"
    
    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    # Resources
    GAP_0 = "rq2_gap_0"
    GAP_1 = "rq2_gap_1"
    GAP_2 = "rq2_gap_2"
    
    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    RQ2_GATE = "rq2_gate"
    
    # Timeout
    TIMEOUT = 4.0

    # --- Phase 1: Resource Checks (LEFT only, serial) ---
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order.
    await robot.acquire(LEFT, GAP_0, TIMEOUT)
    await robot.release_resource(LEFT, GAP_0)
    
    await robot.acquire(LEFT, GAP_1, TIMEOUT)
    await robot.release_resource(LEFT, GAP_1)
    
    await robot.acquire(LEFT, GAP_2, TIMEOUT)
    await robot.release_resource(LEFT, GAP_2)

    # --- Phase 2: Signal and Wait Gate ---
    # Signal rq2_gate exactly once
    gate_receipt = robot.signal(RQ2_GATE)
    
    # Wait immediately after the signal
    # wait_event returns the active EventReceipt
    active_gate_receipt = await robot.wait_event(RQ2_GATE, TIMEOUT)

    # --- Phase 3: Inherited Dual-Arm Mission (Serial) ---
    # The task requires serial scheduling for the inherited mission.
    # We execute LEFT branch fully, then RIGHT branch fully.
    
    # --- LEFT Branch ---
    # 1. Approach (move to source)
    await robot.move(LEFT, LEFT_SOURCE, timeout_s=TIMEOUT)
    # 2. Grasp
    await robot.grasp(LEFT, LEFT_PART)
    # 3. Transport (move to target)
    await robot.move(LEFT, LEFT_TARGET, timeout_s=TIMEOUT)
    # 4. Release
    await robot.release(LEFT, LEFT_PART, LEFT_TARGET)
    # 5. Depart (move to depart)
    await robot.move(LEFT, LEFT_DEPART, timeout_s=TIMEOUT)
    
    # Signal join event for LEFT
    robot.signal(LEFT_READY)

    # --- RIGHT Branch ---
    # 1. Approach (move to source)
    await robot.move(RIGHT, RIGHT_SOURCE, timeout_s=TIMEOUT)
    # 2. Grasp
    await robot.grasp(RIGHT, RIGHT_PART)
    # 3. Transport (move to target)
    await robot.move(RIGHT, RIGHT_TARGET, timeout_s=TIMEOUT)
    # 4. Release
    await robot.release(RIGHT, RIGHT_PART, RIGHT_TARGET)
    # 5. Depart (move to depart)
    await robot.move(RIGHT, RIGHT_DEPART, timeout_s=TIMEOUT)
    
    # Signal join event for RIGHT
    robot.signal(RIGHT_READY)

    # --- Phase 4: Clear Gate ---
    # Clear exactly that version after its assigned protected scope.
    # The scope is the inherited mission.
    robot.clear_event(RQ2_GATE, expected_version=active_gate_receipt.version)
