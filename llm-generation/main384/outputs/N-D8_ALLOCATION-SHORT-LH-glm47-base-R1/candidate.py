import asyncio
import json
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    """
    Task D8_ALLOCATION-SHORT-LH:
    1. Inspect allocation fact to determine which arm is selected.
    2. Selected arm moves to shared_source, grasps shared_part (using observation), 
       moves to shared_target, releases, and departs.
    3. Non-selected arm stays at home.
    4. Both arms must inspect allocation.
    """

    ALLOCATION_FACT_ID = "allocation"
    SHARED_PART_ID = "shared_part"
    
    # Poses
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_DEPART = "left_depart"
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_DEPART = "right_depart"
    POSE_SHARED_SOURCE = "shared_source"
    POSE_SHARED_TARGET = "shared_target"

    # Support Zones
    ZONE_SHARED_SOURCE = "shared_source"
    ZONE_SHARED_TARGET = "shared_target"

    # Timeout for move (default is 4s, explicit range 0.05-30s)
    MOVE_TIMEOUT = 4.0

    async def worker(arm: str):
        # 1. Inspect allocation
        obs: Observation = await robot.inspect(arm, ALLOCATION_FACT_ID)
        
        # Decode value to find selected arm
        data = obs.value
        selected_arm = data.get("selected_arm")
        
        if selected_arm == arm:
            # This arm is selected to transport
            # Move to source (approach)
            await robot.move(arm, POSE_SHARED_SOURCE, timeout_s=MOVE_TIMEOUT)
            
            # Grasp with observation
            await robot.grasp(arm, SHARED_PART_ID, observation=obs)
            
            # Move to target
            await robot.move(arm, POSE_SHARED_TARGET, timeout_s=MOVE_TIMEOUT)
            
            # Release
            await robot.release(arm, SHARED_PART_ID, ZONE_SHARED_TARGET)
            
            # Depart immediately
            if arm == "LEFT":
                await robot.move(arm, POSE_LEFT_DEPART, timeout_s=MOVE_TIMEOUT)
            else:
                await robot.move(arm, POSE_RIGHT_DEPART, timeout_s=MOVE_TIMEOUT)
        else:
            # This arm is not selected, remain at home
            pass

    # Run both workers concurrently
    await asyncio.gather(
        worker("LEFT"),
        worker("RIGHT")
    )
