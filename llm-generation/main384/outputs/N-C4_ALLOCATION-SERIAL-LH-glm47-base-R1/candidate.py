import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    """
    Task: C4_ALLOCATION-SERIAL-LH
    Structure: Variant A (Serial execution of LEFT then RIGHT).
    Goal: Transport shared_part to shared_target using the selected arm.
    """

    # Constants from PUBLIC TASK
    ALLOCATION_FACT_ID = "allocation"
    SHARED_PART_ID = "shared_part"
    SOURCE_POSE = "shared_source"
    TARGET_POSE = "shared_target"
    
    LEFT_HOME = "left_home"
    LEFT_DEPART = "left_depart"
    RIGHT_HOME = "right_home"
    RIGHT_DEPART = "right_depart"

    # Helper to inspect allocation
    async def inspect_allocation(arm: str) -> Observation:
        # Both workers inspect allocation once before choosing branch
        obs = await robot.inspect(arm, ALLOCATION_FACT_ID)
        return obs

    # --- Phase 1: LEFT Worker ---
    # Inspect allocation
    left_obs = await inspect_allocation("LEFT")
    
    # Determine selected arm from observation value
    # Value format: {"item_id": "shared_part", "selected_arm": "LEFT"}
    alloc_data = left_obs.value
    selected_arm = alloc_data["selected_arm"]

    if selected_arm == "LEFT":
        # LEFT is selected: Perform transport
        # 1. Approach (move to source)
        await robot.move("LEFT", SOURCE_POSE)
        
        # 2. Grasp (must provide observation)
        await robot.grasp("LEFT", SHARED_PART_ID, observation=left_obs)
        
        # 3. Transport (move to target)
        await robot.move("LEFT", TARGET_POSE)
        
        # 4. Release
        await robot.release("LEFT", SHARED_PART_ID, TARGET_POSE)
        
        # 5. Depart (immediate separating departure)
        await robot.move("LEFT", LEFT_DEPART)
    else:
        # LEFT is not selected: Remain at home (no move/grasp/release calls)
        pass

    # --- Phase 2: RIGHT Worker ---
    # Serial execution: RIGHT runs after LEFT finishes.
    # Inspect allocation
    right_obs = await inspect_allocation("RIGHT")
    
    # Re-check selected arm (though logically static, we follow the spec)
    # Note: If LEFT was selected, RIGHT must not act.
    # If RIGHT was selected, LEFT did nothing, and RIGHT must act.
    
    if selected_arm == "RIGHT":
        # RIGHT is selected: Perform transport
        # 1. Approach
        await robot.move("RIGHT", SOURCE_POSE)
        
        # 2. Grasp
        await robot.grasp("RIGHT", SHARED_PART_ID, observation=right_obs)
        
        # 3. Transport
        await robot.move("RIGHT", TARGET_POSE)
        
        # 4. Release
        await robot.release("RIGHT", SHARED_PART_ID, TARGET_POSE)
        
        # 5. Depart
        await robot.move("RIGHT", RIGHT_DEPART)
    else:
        # RIGHT is not selected: Remain at home
        pass
