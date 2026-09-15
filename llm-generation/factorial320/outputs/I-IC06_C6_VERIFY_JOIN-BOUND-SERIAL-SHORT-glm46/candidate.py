import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants extracted from PUBLIC TASK
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
    
    EVENT_LEFT_READY = "left_ready"
    EVENT_RIGHT_READY = "right_ready"
    EVENT_GATE = "rq2_gate"
    
    TIMEOUT_S = 4.0 # default_move_timeout_s

    # --- Phase 1: Resource Checks (Serial, LEFT only) ---
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # "Complete all three rq2_gap resource checks before signalling rq2_gate"
    
    await robot.acquire(ARM_LEFT, RES_GAP_0, TIMEOUT_S)
    await robot.release_resource(ARM_LEFT, RES_GAP_0)
    
    await robot.acquire(ARM_LEFT, RES_GAP_1, TIMEOUT_S)
    await robot.release_resource(ARM_LEFT, RES_GAP_1)
    
    await robot.acquire(ARM_LEFT, RES_GAP_2, TIMEOUT_S)
    await robot.release_resource(ARM_LEFT, RES_GAP_2)

    # --- Phase 2: Signal Gate ---
    # "Signal rq2_gate exactly once"
    gate_receipt = robot.signal(EVENT_GATE)
    
    # --- Phase 3: Wait Gate ---
    # "wait its exact active receipt exactly once"
    # "wait immediately after the signal"
    # "Use serial scheduling for both the inherited dual-arm mission and the rq2_gate producer/consumer."
    # This implies we wait for the gate we just signaled before proceeding with the main mission.
    await robot.wait_event(EVENT_GATE, TIMEOUT_S)

    # --- Phase 4: Inherited Dual-Arm Mission (Serial) ---
    # "both parts at their own target; both arms at departure and empty"
    # "Use serial scheduling for both the inherited dual-arm mission"
    
    # LEFT Arm Sequence
    # 1. Move to source (Approach)
    await robot.move(ARM_LEFT, POSE_LEFT_SOURCE, timeout_s=TIMEOUT_S)
    # 2. Grasp left_part
    await robot.grasp(ARM_LEFT, OBJ_LEFT)
    # 3. Move to target
    await robot.move(ARM_LEFT, POSE_LEFT_TARGET, timeout_s=TIMEOUT_S)
    # 4. Release left_part
    await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
    # 5. Move to depart
    await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_S)

    # RIGHT Arm Sequence
    # 1. Move to source (Approach)
    await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE, timeout_s=TIMEOUT_S)
    # 2. Grasp right_part
    await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
    # 3. Move to target
    await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET, timeout_s=TIMEOUT_S)
    # 4. Release right_part
    await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_TARGET)
    # 5. Move to depart
    await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART, timeout_s=TIMEOUT_S)

    # --- Phase 5: Clear Gate ---
    # "Keep rq2_gate active while executing the complete inherited dual-arm mission after the wait"
    # "clear exactly that version after its assigned protected scope"
    # "rq2_gate inactive at return"
    robot.clear_event(EVENT_GATE, expected_version=gate_receipt.version)
