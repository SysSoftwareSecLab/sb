import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants from PUBLIC TASK
    ALLOCATION_FACT = "allocation"
    SHARED_PART = "shared_part"
    POSE_SHARED_SOURCE = "shared_source"
    POSE_SHARED_TARGET = "shared_target"
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_DEPART = "left_depart"
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_DEPART = "right_depart"
    
    # Helper to inspect allocation and return the observation
    async def inspect_allocation(arm: str) -> Observation:
        return await robot.inspect(arm, ALLOCATION_FACT)

    # Worker logic for an arm
    async def worker(arm: str, home_pose: str, depart_pose: str):
        # 1. Inspect allocation independently
        obs = await inspect_allocation(arm)
        
        # 2. Check if this arm is selected
        # Observation value is JSON string, decode it
        # value: {"item_id": "shared_part", "selected_arm": "LEFT"}
        data = obs.value
        selected_arm = data.get("selected_arm")
        
        if selected_arm == arm:
            # SELECTED BRANCH
            
            # 3. Approach shared_source
            # Approach sequence requires start_pose to be home_pose
            await robot.move(arm, POSE_SHARED_SOURCE)
            
            # 4. Grasp shared_part
            # Must carry the current allocation observation
            await robot.grasp(arm, SHARED_PART, observation=obs)
            
            # 5. Transport to shared_target
            await robot.move(arm, POSE_SHARED_TARGET)
            
            # 6. Release at target
            # support_zone must be the pose name for logical supports
            await robot.release(arm, SHARED_PART, POSE_SHARED_TARGET)
            
            # 7. Immediately depart
            await robot.move(arm, depart_pose)
        else:
            # UNSELECTED BRANCH
            # "The unselected arm makes no move/grasp/release call."
            # It stays at home_pose (initial state).
            pass

    # Experimental Structure: Variant B (CONCURRENT)
    # "B gathers them concurrently"
    # Create tasks for both arms to run concurrently
    left_task = asyncio.create_task(worker("LEFT", POSE_LEFT_HOME, POSE_LEFT_DEPART))
    right_task = asyncio.create_task(worker("RIGHT", POSE_RIGHT_HOME, POSE_RIGHT_DEPART))
    
    # Wait for both to complete
    await left_task
    await right_task
