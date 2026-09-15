import asyncio
import json
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants derived from PUBLIC TASK
    ALLOCATION_FACT_ID = "allocation"
    SHARED_PART_ID = "shared_part"
    SOURCE_POSE = "shared_source"
    TARGET_POSE = "shared_target"
    
    LEFT_HOME = "left_home"
    LEFT_DEPART = "left_depart"
    RIGHT_HOME = "right_home"
    RIGHT_DEPART = "right_depart"
    
    MOVE_TIMEOUT = 4.0
    EVENT_TIMEOUT = 5.0
    
    # Helper to determine selected arm from observation
    def get_selected_arm(obs: Observation) -> str:
        data = obs.value
        return data["selected_arm"]

    # Worker coroutine for a specific arm
    async def worker(arm: str, home_pose: str, depart_pose: str):
        # 1. Both workers independently inspect allocation once before choosing their own branch.
        # Using inspect as per API to get the fact value.
        alloc_obs: Observation = await robot.inspect(arm, ALLOCATION_FACT_ID)
        
        selected_arm = get_selected_arm(alloc_obs)
        
        if arm == selected_arm:
            # Selected arm path
            # 2. Only the selected arm may propose approach, grasp, or transport.
            
            # Approach sequence: start_pose -> interaction_pose
            # Must be followed immediately by grasp.
            await robot.move(arm, SOURCE_POSE, timeout_s=MOVE_TIMEOUT)
            
            # Grasp: Must carry the current allocation observation
            await robot.grasp(arm, SHARED_PART_ID, observation=alloc_obs)
            
            # Transport: Move to target
            await robot.move(arm, TARGET_POSE, timeout_s=MOVE_TIMEOUT)
            
            # Release at target
            await robot.release(arm, SHARED_PART_ID, TARGET_POSE)
            
            # Immediately depart
            await robot.move(arm, depart_pose, timeout_s=MOVE_TIMEOUT)
        else:
            # Unselected arm path
            # "The unselected arm makes no move/grasp/release call."
            # It must end at its home pose (initial state) or depart if required by goal?
            # Goal: "nonselected RIGHT empty at right_home."
            # Since it starts at home and does nothing, it satisfies the goal.
            pass

    # Experimental structure: B gathers them concurrently.
    # Create tasks for both arms to run concurrently.
    left_task = asyncio.create_task(worker("LEFT", LEFT_HOME, LEFT_DEPART))
    right_task = asyncio.create_task(worker("RIGHT", RIGHT_HOME, RIGHT_DEPART))
    
    # Wait for both workers to complete
    await left_task
    await right_task
