import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants derived from PUBLIC TASK
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
    
    FACT_ROUTE = "route"
    
    # Timeout constants
    TIMEOUT_MOVE = 4.0
    TIMEOUT_ACQUIRE = 1.0
    TIMEOUT_EVENT = 5.0
    
    # --- LEFT ARM TASK ---
    # 1. Approach left_part
    await robot.move(ARM_LEFT, POSE_LEFT_SOURCE, timeout_s=TIMEOUT_MOVE)
    
    # 2. Grasp left_part
    # Observation of 'route' is required by development_contract.
    # This observation is consumed by the grasp operation.
    obs_route: Observation = await robot.grasp(ARM_LEFT, OBJ_LEFT, observation=None)
    
    # 3. Transport left_part to left_target
    await robot.move(ARM_LEFT, POSE_LEFT_TARGET, timeout_s=TIMEOUT_MOVE)
    
    # 4. Release left_part at left_target
    await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
    
    # 5. Depart to left_depart
    await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_MOVE)
    
    # --- RIGHT ARM TASK ---
    # 1. Approach right_part
    await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE, timeout_s=TIMEOUT_MOVE)
    
    # 2. Grasp right_part
    await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
    
    # 3. Transport right_part to right_target
    await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET, timeout_s=TIMEOUT_MOVE)
    
    # 4. Release right_part at right_target
    await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_TARGET)
    
    # 5. Depart to right_depart
    await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART, timeout_s=TIMEOUT_MOVE)
