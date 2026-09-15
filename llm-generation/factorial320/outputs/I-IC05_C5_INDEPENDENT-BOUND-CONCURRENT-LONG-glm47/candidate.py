import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
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
    
    EVENT_GATE = "rq2_gate"
    
    TIMEOUT_ACQUIRE = 1.0
    TIMEOUT_WAIT = 5.0
    
    # Helper to acquire and release a resource
    async def check_resource(arm: str, res_id: str):
        await robot.acquire(arm, res_id, TIMEOUT_ACQUIRE)
        await robot.release_resource(arm, res_id)
    
    # 1. Signal rq2_gate
    gate_receipt = robot.signal(EVENT_GATE)
    
    # 2. Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 with LEFT in numeric order
    await check_resource(ARM_LEFT, RES_GAP_0)
    await check_resource(ARM_LEFT, RES_GAP_1)
    await check_resource(ARM_LEFT, RES_GAP_2)
    
    # 3. Wait for rq2_gate (exact active receipt)
    # Note: wait_event returns the active receipt, which matches the one we signaled.
    await robot.wait_event(EVENT_GATE, TIMEOUT_WAIT)
    
    # 4. Execute the inherited dual-arm mission concurrently
    # Mission: Move parts from source to target, then depart.
    
    async def left_arm_mission():
        # Approach
        await robot.move(ARM_LEFT, POSE_LEFT_SOURCE)
        # Grasp
        await robot.grasp(ARM_LEFT, OBJ_LEFT)
        # Move to target
        await robot.move(ARM_LEFT, POSE_LEFT_TARGET)
        # Release
        await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
        # Depart (immediate separating departure)
        await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
    
    async def right_arm_mission():
        # Approach
        await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE)
        # Grasp
        await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
        # Move to target
        await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET)
        # Release
        await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_TARGET)
        # Depart (immediate separating departure)
        await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART)
    
    # Run concurrently
    await asyncio.gather(left_arm_mission(), right_arm_mission())
    
    # 5. Clear rq2_gate after the mission
    robot.clear_event(EVENT_GATE, expected_version=gate_receipt.version)
