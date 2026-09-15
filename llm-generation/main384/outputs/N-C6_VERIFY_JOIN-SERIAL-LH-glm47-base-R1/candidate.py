import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants from PUBLIC TASK
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
    
    FACT_LEFT_VERIFICATION = "left_verification"
    FACT_RIGHT_VERIFICATION = "right_verification"
    
    EVENT_LEFT_READY = "left_ready"
    EVENT_RIGHT_READY = "right_ready"
    
    # Helper to verify and signal
    async def verify_and_signal(arm: str, object_id: str, fact_id: str, event_id: str):
        # Inspect the verification fact
        obs: Observation = await robot.inspect(arm, fact_id)
        
        # Signal readiness
        receipt: EventReceipt = robot.signal(event_id, item_id=object_id)
        
        # Wait for the other arm to be ready (Join Point)
        # We need to wait for the event that is NOT the one we just signaled.
        other_event_id = EVENT_RIGHT_READY if event_id == EVENT_LEFT_READY else EVENT_LEFT_READY
        await robot.wait_event(other_event_id, timeout_s=30)
        
        return receipt

    # Define the tasks for each arm
    async def left_arm_task():
        # 1. Approach
        await robot.move(ARM_LEFT, POSE_LEFT_SOURCE)
        
        # 2. Grasp
        await robot.grasp(ARM_LEFT, OBJ_LEFT)
        
        # 3. Verify and Signal (Wait for Right)
        receipt = await verify_and_signal(ARM_LEFT, OBJ_LEFT, FACT_LEFT_VERIFICATION, EVENT_LEFT_READY)
        
        # 4. Move to Target using receipt
        await robot.move(ARM_LEFT, POSE_LEFT_TARGET, receipt=receipt)
        
        # 5. Release
        await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
        
        # 6. Depart
        await robot.move(ARM_LEFT, POSE_LEFT_DEPART)

    async def right_arm_task():
        # 1. Approach
        await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE)
        
        # 2. Grasp
        await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
        
        # 3. Verify and Signal (Wait for Left)
        receipt = await verify_and_signal(ARM_RIGHT, OBJ_RIGHT, FACT_RIGHT_VERIFICATION, EVENT_RIGHT_READY)
        
        # 4. Move to Target using receipt
        await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET, receipt=receipt)
        
        # 5. Release
        await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_TARGET)
        
        # 6. Depart
        await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART)

    # Run tasks concurrently
    await asyncio.gather(left_arm_task(), right_arm_task())
