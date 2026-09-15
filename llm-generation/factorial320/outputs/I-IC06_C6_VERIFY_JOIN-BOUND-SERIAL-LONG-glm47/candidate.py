import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_LEFT_TARGET = "left_target"
    POSE_LEFT_DEPART = "left_depart"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_TARGET = "right_target"
    POSE_RIGHT_DEPART = "right_depart"
    
    OBJ_LEFT = "left_part"
    OBJ_RIGHT = "right_part"
    
    RES_GAP_0 = "rq2_gap_0"
    RES_GAP_1 = "rq2_gap_1"
    RES_GAP_2 = "rq2_gap_2"
    
    EVT_LEFT_READY = "left_ready"
    EVT_RIGHT_READY = "right_ready"
    EVT_GATE = "rq2_gate"
    
    TIMEOUT_S = 4.0
    
    # --- Phase 1: Signal Join Events ---
    # Signal left_ready and right_ready to indicate readiness
    left_ready_receipt = robot.signal(EVT_LEFT_READY)
    right_ready_receipt = robot.signal(EVT_RIGHT_READY)
    
    # --- Phase 2: Signal Gate and Acquire Resources (Serial) ---
    # "Signal rq2_gate exactly once"
    gate_receipt = robot.signal(EVT_GATE)
    
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    
    # Acquire rq2_gap_0
    await robot.acquire(ARM_LEFT, RES_GAP_0, TIMEOUT_S)
    await robot.release_resource(ARM_LEFT, RES_GAP_0)
    
    # Acquire rq2_gap_1
    await robot.acquire(ARM_LEFT, RES_GAP_1, TIMEOUT_S)
    await robot.release_resource(ARM_LEFT, RES_GAP_1)
    
    # Acquire rq2_gap_2
    await robot.acquire(ARM_LEFT, RES_GAP_2, TIMEOUT_S)
    await robot.release_resource(ARM_LEFT, RES_GAP_2)
    
    # --- Phase 3: Wait for Gate ---
    # "wait its exact active receipt exactly once"
    # "only then wait for rq2_gate"
    await robot.wait_event(EVT_GATE, TIMEOUT_S)
    
    # --- Phase 4: Inherited Dual-Arm Mission (Serial) ---
    # "Use serial scheduling for both the inherited dual-arm mission"
    # "Keep rq2_gate active while executing the complete inherited dual-arm mission"
    
    # LEFT Arm Sequence
    # Move to source (Approach)
    await robot.move(ARM_LEFT, POSE_LEFT_SOURCE, timeout_s=TIMEOUT_S)
    # Grasp left_part
    await robot.grasp(ARM_LEFT, OBJ_LEFT)
    # Move to target
    await robot.move(ARM_LEFT, POSE_LEFT_TARGET, timeout_s=TIMEOUT_S)
    # Release left_part
    await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
    # Move to depart
    await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_S)
    
    # RIGHT Arm Sequence
    # Move to source (Approach)
    await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE, timeout_s=TIMEOUT_S)
    # Grasp right_part
    await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
    # Move to target
    await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET, timeout_s=TIMEOUT_S)
    # Release right_part
    await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_TARGET)
    # Move to depart
    await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART, timeout_s=TIMEOUT_S)
    
    # --- Phase 5: Clear Gate ---
    # "clear exactly that version after its assigned protected scope"
    # "rq2_gate inactive at return"
    robot.clear_event(EVT_GATE, expected_version=gate_receipt.version)
