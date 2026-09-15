import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    """
    Executes the C4_ALLOCATION-SERIAL-LH task.
    Variant A: Serial execution of candidate LEFT then RIGHT.
    """
    
    # Constants from PUBLIC TASK
    ALLOCATION_FACT_ID = "allocation"
    SHARED_PART_ID = "shared_part"
    LEFT_ARM = "LEFT"
    RIGHT_ARM = "RIGHT"
    
    POSES = {
        "left_home": "left_home",
        "left_depart": "left_depart",
        "right_home": "right_home",
        "right_depart": "right_depart",
        "shared_source": "shared_source",
        "shared_target": "shared_target"
    }
    
    # Helper to inspect allocation and return the observation
    async def inspect_allocation(arm: str) -> Observation:
        # Both workers independently inspect allocation once before choosing their own branch.
        # Using inspect as per API to get the fact value.
        obs = await robot.inspect(arm, ALLOCATION_FACT_ID)
        return obs

    # --- Candidate LEFT ---
    # Inspect allocation
    obs_left = await inspect_allocation(LEFT_ARM)
    
    # Check if LEFT is selected
    # obs.value is the decoded JSON: {"item_id": "shared_part", "selected_arm": "LEFT"}
    is_left_selected = (obs_left.value.get("selected_arm") == LEFT_ARM)
    
    if is_left_selected:
        # Sequence: Approach (move) -> Grasp -> Transport (move) -> Release -> Depart (move)
        # Approach: move from left_home to shared_source
        await robot.move(LEFT_ARM, POSES["shared_source"])
        
        # Grasp: Must carry the current allocation observation
        await robot.grasp(LEFT_ARM, SHARED_PART_ID, observation=obs_left)
        
        # Transport: move from shared_source to shared_target
        await robot.move(LEFT_ARM, POSES["shared_target"])
        
        # Release: at shared_target
        await robot.release(LEFT_ARM, SHARED_PART_ID, POSES["shared_target"])
        
        # Depart: immediate separating departure
        await robot.move(LEFT_ARM, POSES["left_depart"])
    else:
        # Unselected arm makes no move/grasp/release call.
        # It stays at home (left_home).
        pass

    # --- Candidate RIGHT ---
    # Inspect allocation
    obs_right = await inspect_allocation(RIGHT_ARM)
    
    # Check if RIGHT is selected
    is_right_selected = (obs_right.value.get("selected_arm") == RIGHT_ARM)
    
    if is_right_selected:
        # Sequence: Approach (move) -> Grasp -> Transport (move) -> Release -> Depart (move)
        # Approach: move from right_home to shared_source
        await robot.move(RIGHT_ARM, POSES["shared_source"])
        
        # Grasp: Must carry the current allocation observation
        await robot.grasp(RIGHT_ARM, SHARED_PART_ID, observation=obs_right)
        
        # Transport: move from shared_source to shared_target
        await robot.move(RIGHT_ARM, POSES["shared_target"])
        
        # Release: at shared_target
        await robot.release(RIGHT_ARM, SHARED_PART_ID, POSES["shared_target"])
        
        # Depart: immediate separating departure
        await robot.move(RIGHT_ARM, POSES["right_depart"])
    else:
        # Unselected arm makes no move/grasp/release call.
        # It stays at home (right_home).
        pass
