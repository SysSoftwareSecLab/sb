import asyncio
from bridge_robot_api import Robot

async def run_task(robot: Robot) -> None:
    """
    Executes the CONCURRENT task for layout LH.
    Two independent arms move parts from source to target concurrently.
    """
    
    # Define constants from the task specification
    LEFT_ARM = "LEFT"
    RIGHT_ARM = "RIGHT"
    
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    LEFT_HOME = "left_home"
    RIGHT_HOME = "right_home"
    
    LEFT_SOURCE = "left_source"
    RIGHT_SOURCE = "right_source"
    
    LEFT_TARGET = "left_target"
    RIGHT_TARGET = "right_target"
    
    LEFT_DEPART = "left_depart"
    RIGHT_DEPART = "right_depart"
    
    # Helper coroutine for a single arm's workflow
    async def arm_workflow(arm: str, part: str, home: str, source: str, target: str, depart: str):
        # 1. Move to source (Approach)
        await robot.move(arm, source)
        
        # 2. Grasp the part
        await robot.grasp(arm, part)
        
        # 3. Move to target
        await robot.move(arm, target)
        
        # 4. Release the part
        await robot.release(arm, part, target)
        
        # 5. Move to departure pose
        await robot.move(arm, depart)

    # Create concurrent tasks for both arms
    left_task = asyncio.create_task(
        arm_workflow(LEFT_ARM, LEFT_PART, LEFT_HOME, LEFT_SOURCE, LEFT_TARGET, LEFT_DEPART)
    )
    
    right_task = asyncio.create_task(
        arm_workflow(RIGHT_ARM, RIGHT_PART, RIGHT_HOME, RIGHT_SOURCE, RIGHT_TARGET, RIGHT_DEPART)
    )
    
    # Wait for both tasks to complete
    await left_task
    await right_task
