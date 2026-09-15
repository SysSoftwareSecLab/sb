import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants from PUBLIC TASK
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    OBJ_LEFT = "left_part"
    OBJ_RIGHT = "right_part"
    
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_LEFT_WAIT = "left_wait"
    POSE_LEFT_TARGET = "left_target"
    POSE_LEFT_DEPART = "left_depart"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_TARGET = "right_target"
    POSE_RIGHT_DEPART = "right_depart"
    
    POSE_INSPECTION = "inspection"
    POSE_REWORK = "rework"
    POSE_REWORK_WAIT = "rework_wait"
    
    FACT_QUALITY = "quality"
    
    TIMEOUT_S = 4.0
    
    # --- Phase 1: Initial Pickup ---
    # LEFT moves to source and grasps left_part
    await robot.move(ARM_LEFT, POSE_LEFT_SOURCE, timeout_s=TIMEOUT_S)
    # No observation required for initial pickup
    await robot.grasp(ARM_LEFT, OBJ_LEFT)
    
    # RIGHT moves to source and grasps right_part
    await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE, timeout_s=TIMEOUT_S)
    await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
    
    # --- Phase 2: LEFT places at inspection ---
    # LEFT moves to inspection
    await robot.move(ARM_LEFT, POSE_INSPECTION, timeout_s=TIMEOUT_S)
    # LEFT releases left_part at inspection
    # This triggers invalidation of 'quality' fact (version 1 -> 2)
    await robot.release(ARM_LEFT, OBJ_LEFT, POSE_INSPECTION)
    
    # LEFT must depart immediately (same virtual time) to satisfy order constraint
    # "LEFT places at inspection and immediately departs before RIGHT inspects quality"
    await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_S)
    
    # --- Phase 3: RIGHT inspects quality ---
    # RIGHT moves to inspection (holding right_part)
    await robot.move(ARM_RIGHT, POSE_INSPECTION, timeout_s=TIMEOUT_S)
    
    # RIGHT inspects quality fact
    # This returns Observation with version 2 (incremented by LEFT's release)
    quality_obs: Observation = await robot.inspect(ARM_RIGHT, FACT_QUALITY)
    
    # Determine target based on observation value
    # value: {"accept_by_pass": [true, true], "item_id": "left_part"}
    # Pass index 0 (first inspection pass)
    accept_by_pass = quality_obs.value["accept_by_pass"]
    is_accepted = accept_by_pass[0]
    
    # --- Phase 4: LEFT completes based on inspection result ---
    if is_accepted:
        # Branch A: Accepted on first pass
        # LEFT moves from depart to inspection (approach)
        await robot.move(ARM_LEFT, POSE_LEFT_WAIT, timeout_s=TIMEOUT_S)
        # Grasp requires observation from RIGHT (producer of quality fact)
        # "At each inspection pass use the newly issued current quality record on LEFT inspection pickup"
        await robot.grasp(ARM_LEFT, OBJ_LEFT, observation=quality_obs)
        
        # Move to target and release
        await robot.move(ARM_LEFT, POSE_LEFT_TARGET, timeout_s=TIMEOUT_S)
        await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
        
        # Depart to terminal
        await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_S)
    else:
        # Branch B: Rejected on first pass -> Rework
        # LEFT moves from depart to rework (approach)
        await robot.move(ARM_LEFT, POSE_REWORK_WAIT, timeout_s=TIMEOUT_S)
        # Grasp requires observation
        await robot.grasp(ARM_LEFT, OBJ_LEFT, observation=quality_obs)
        
        # Move to rework zone and release
        await robot.move(ARM_LEFT, POSE_REWORK, timeout_s=TIMEOUT_S)
        await robot.release(ARM_LEFT, OBJ_LEFT, POSE_REWORK)
        
        # Depart immediately
        await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_S)
        
        # --- Phase 5: RIGHT re-inspects ---
        # RIGHT must inspect again to issue new record for second pass pickup
        # "RIGHT issues each inspection observation"
        # This fetches the new version (version 3)
        quality_obs_v2: Observation = await robot.inspect(ARM_RIGHT, FACT_QUALITY)
        
        # Check second pass result (index 1)
        # Spec says "B on second", so this should be true
        is_accepted_v2 = quality_obs_v2.value["accept_by_pass"][1]
        
        # LEFT picks up from rework
        await robot.move(ARM_LEFT, POSE_REWORK_WAIT, timeout_s=TIMEOUT_S)
        await robot.grasp(ARM_LEFT, OBJ_LEFT, observation=quality_obs_v2)
        
        # Move to target and release
        await robot.move(ARM_LEFT, POSE_LEFT_TARGET, timeout_s=TIMEOUT_S)
        await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
        
        # Depart to terminal
        await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_S)
    
    # --- Phase 6: RIGHT completes ---
    # RIGHT moves to target and releases right_part
    await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET, timeout_s=TIMEOUT_S)
    await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_TARGET)
    
    # RIGHT departs to terminal
    await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART, timeout_s=TIMEOUT_S)
