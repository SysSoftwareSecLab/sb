import asyncio

async def run_task(robot):
    """
    Executes the C6_VERIFY_JOIN-SERIAL-L0 task.
    Structure:
    1. LEFT arm performs its verification sequence (Inspect -> Move -> Grasp -> Move -> Release -> Depart).
    2. RIGHT arm performs its verification sequence (Inspect -> Move -> Grasp -> Move -> Release -> Depart).
    3. Join events are signaled to satisfy the development contract.
    """

    # Constants extracted from PUBLIC TASK
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    OBJ_LEFT = "left_part"
    OBJ_RIGHT = "right_part"
    
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_LEFT_TARGET = "left_target"
    POSE_LEFT_DEPART = "left_depart"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_TARGET = "right_target"
    POSE_RIGHT_DEPART = "right_depart"
    
    FACT_LEFT_VERIFICATION = "left_verification"
    FACT_RIGHT_VERIFICATION = "right_verification"
    
    EVENT_LEFT_READY = "left_ready"
    EVENT_RIGHT_READY = "right_ready"
    
    TIMEOUT_S = 4.0  # default_move_timeout_s

    async def run_left_sequence():
        # 1. Inspect verification fact
        obs_left = await robot.inspect(ARM_LEFT, FACT_LEFT_VERIFICATION)
        
        # 2. Move to source (Approach)
        await robot.move(ARM_LEFT, POSE_LEFT_SOURCE, timeout_s=TIMEOUT_S)
        
        # 3. Grasp object
        # Observation is passed as per task requirements for verification
        await robot.grasp(ARM_LEFT, OBJ_LEFT, observation=obs_left)
        
        # 4. Move to target
        await robot.move(ARM_LEFT, POSE_LEFT_TARGET, timeout_s=TIMEOUT_S)
        
        # 5. Release object
        await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
        
        # 6. Depart to final pose
        await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_S)
        
        # 7. Signal join event
        robot.signal(EVENT_LEFT_READY)

    async def run_right_sequence():
        # 1. Inspect verification fact
        obs_right = await robot.inspect(ARM_RIGHT, FACT_RIGHT_VERIFICATION)
        
        # 2. Move to source (Approach)
        await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE, timeout_s=TIMEOUT_S)
        
        # 3. Grasp object
        await robot.grasp(ARM_RIGHT, OBJ_RIGHT, observation=obs_right)
        
        # 4. Move to target
        await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET, timeout_s=TIMEOUT_S)
        
        # 5. Release object
        await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_TARGET)
        
        # 6. Depart to final pose
        await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART, timeout_s=TIMEOUT_S)
        
        # 7. Signal join event
        robot.signal(EVENT_RIGHT_READY)

    # Execute sequences serially as required by CONCURRENCY=SERIAL
    await run_left_sequence()
    await run_right_sequence()
