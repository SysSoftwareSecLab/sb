import asyncio

async def run_task(robot):
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
    
    OBJ_LEFT_PART = "left_part"
    OBJ_RIGHT_PART = "right_part"
    
    RES_GAP_0 = "rq2_gap_0"
    RES_GAP_1 = "rq2_gap_1"
    RES_GAP_2 = "rq2_gap_2"
    
    EVENT_GATE = "rq2_gate"
    
    TIMEOUT_S = 4.0  # default_move_timeout_s

    # 1. Signal rq2_gate
    # "Signal rq2_gate exactly once"
    gate_receipt = robot.signal(EVENT_GATE)
    
    # 2. Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # "never retain them at return"
    # "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    
    # Acquire 0
    await robot.acquire(ARM_LEFT, RES_GAP_0, TIMEOUT_S)
    await robot.release_resource(ARM_LEFT, RES_GAP_0)
    
    # Acquire 1
    await robot.acquire(ARM_LEFT, RES_GAP_1, TIMEOUT_S)
    await robot.release_resource(ARM_LEFT, RES_GAP_1)
    
    # Acquire 2
    await robot.acquire(ARM_LEFT, RES_GAP_2, TIMEOUT_S)
    await robot.release_resource(ARM_LEFT, RES_GAP_2)
    
    # 3. Wait for rq2_gate
    # "wait its exact active receipt exactly once"
    # "only then wait for rq2_gate"
    active_gate_receipt = await robot.wait_event(EVENT_GATE, TIMEOUT_S)
    
    # 4. Execute the inherited dual-arm mission
    # "Keep rq2_gate active while executing the complete inherited dual-arm mission after the wait"
    # "Use serial scheduling for both the inherited dual-arm mission"
    # Goal: "both parts at their own target; both arms at departure and empty"
    
    # LEFT ARM MISSION
    # Move to source (Approach)
    await robot.move(ARM_LEFT, POSE_LEFT_SOURCE, timeout_s=TIMEOUT_S)
    # Grasp left_part
    await robot.grasp(ARM_LEFT, OBJ_LEFT_PART)
    # Move to target
    await robot.move(ARM_LEFT, POSE_LEFT_TARGET, timeout_s=TIMEOUT_S)
    # Release left_part
    await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_LEFT_TARGET)
    # Move to depart
    await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_S)
    
    # RIGHT ARM MISSION
    # Move to source (Approach)
    await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE, timeout_s=TIMEOUT_S)
    # Grasp right_part
    await robot.grasp(ARM_RIGHT, OBJ_RIGHT_PART)
    # Move to target
    await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET, timeout_s=TIMEOUT_S)
    # Release right_part
    await robot.release(ARM_RIGHT, OBJ_RIGHT_PART, POSE_RIGHT_TARGET)
    # Move to depart
    await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART, timeout_s=TIMEOUT_S)
    
    # 5. Clear rq2_gate
    # "clear exactly that version after its assigned protected scope"
    # "rq2_gate inactive at return"
    robot.clear_event(EVENT_GATE, expected_version=active_gate_receipt.version)
