import asyncio
from bridge_robot_api import Robot, MotionFault, TimeoutError

async def run_task(robot: Robot):
    # Constants from PUBLIC TASK
    FIXTURE = "fixture"
    TOOL = "tool"
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
    
    # Support zones
    LEFT_SOURCE_ZONE = "left_source"
    LEFT_TARGET_ZONE = "left_target"
    RIGHT_SOURCE_ZONE = "right_source"
    RIGHT_TARGET_ZONE = "right_target"

    async def worker(arm: str, home: str, source: str, target: str, depart: str, part: str, source_zone: str, target_zone: str):
        # Acquire resources in order: fixture then tool
        # Use try/finally to ensure release on timeout
        acquired = []
        try:
            await robot.acquire(arm, FIXTURE, 30.0)
            acquired.append(FIXTURE)
            await robot.acquire(arm, TOOL, 30.0)
            acquired.append(TOOL)
            
            # Move to home (start of approach sequence)
            await robot.move(arm, home)
            
            # Approach sequence: start_pose -> interaction_pose
            # Must immediately call grasp after move completes
            await robot.move(arm, source)
            await robot.grasp(arm, part)
            
            # Transport to target
            await robot.move(arm, target)
            
            # Release at target
            await robot.release(arm, part, target_zone)
            
            # Immediate separating departure
            await robot.move(arm, depart)
            
        finally:
            # Release resources in reverse order or any order, ensuring OFF mode
            # set_mode to OFF is required before release_resource
            for res in reversed(acquired):
                await robot.set_mode(arm, res, "OFF")
                await robot.release_resource(arm, res)

    # Scenario B: Launch both workers concurrently using the same acquisition order
    await asyncio.gather(
        worker(LEFT, LEFT_HOME, LEFT_SOURCE, LEFT_TARGET, LEFT_DEPART, LEFT_PART, LEFT_SOURCE_ZONE, LEFT_TARGET_ZONE),
        worker(RIGHT, RIGHT_HOME, RIGHT_SOURCE, RIGHT_TARGET, RIGHT_DEPART, RIGHT_PART, RIGHT_SOURCE_ZONE, RIGHT_TARGET_ZONE)
    )
