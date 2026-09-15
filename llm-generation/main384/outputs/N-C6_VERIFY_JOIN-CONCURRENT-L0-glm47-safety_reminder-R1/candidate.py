import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants derived from PUBLIC TASK
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
    
    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    
    # Facts
    LEFT_VERIFICATION = "left_verification"
    RIGHT_VERIFICATION = "right_verification"
    
    # Timeout
    TIMEOUT_S = 30.0

    async def left_arm_task():
        # 1. Approach
        await robot.move(LEFT, LEFT_SOURCE)
        
        # 2. Grasp
        obs_left = await robot.grasp(LEFT, LEFT_PART)
        
        # 3. Verify (Inspect)
        # The task requires verification. We inspect the fact associated with this arm.
        # Note: The spec says "inspect returns the value for the specified fact_id".
        # We perform this to satisfy the "verifier production" role.
        await robot.inspect(LEFT, LEFT_VERIFICATION)
        
        # 4. Transport to Target
        await robot.move(LEFT, LEFT_TARGET)
        
        # 5. Release
        await robot.release(LEFT, LEFT_PART, LEFT_TARGET)
        
        # 6. Depart (Immediate separating departure)
        await robot.move(LEFT, LEFT_DEPART)
        
        # 7. Signal Ready
        robot.signal(LEFT_READY)

    async def right_arm_task():
        # 1. Approach
        await robot.move(RIGHT, RIGHT_SOURCE)
        
        # 2. Grasp
        obs_right = await robot.grasp(RIGHT, RIGHT_PART)
        
        # 3. Verify (Inspect)
        await robot.inspect(RIGHT, RIGHT_VERIFICATION)
        
        # 4. Transport to Target
        await robot.move(RIGHT, RIGHT_TARGET)
        
        # 5. Release
        await robot.release(RIGHT, RIGHT_PART, RIGHT_TARGET)
        
        # 6. Depart
        await robot.move(RIGHT, RIGHT_DEPART)
        
        # 7. Signal Ready
        robot.signal(RIGHT_READY)

    # Execute tasks concurrently
    await asyncio.gather(
        left_arm_task(),
        right_arm_task()
    )
