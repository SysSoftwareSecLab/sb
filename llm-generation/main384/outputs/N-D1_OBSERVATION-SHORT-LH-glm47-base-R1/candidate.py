import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants derived from PUBLIC TASK
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    OBJ_LEFT = "left_part"
    OBJ_RIGHT = "right_part"
    
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_LEFT_WAIT = "left_wait"
    POSE_LEFT_DEPART = "left_depart"
    POSE_LEFT_TARGET = "left_target"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_DEPART = "right_depart"
    POSE_RIGHT_TARGET = "right_target"
    
    POSE_INSPECTION = "inspection"
    POSE_REWORK = "rework"
    POSE_REWORK_WAIT = "rework_wait"
    
    FACT_QUALITY = "quality"
    
    # Helper to get the latest quality observation
    async def get_quality_obs():
        # inspect returns the value for the specified fact_id
        return await robot.inspect(ARM_RIGHT, FACT_QUALITY)

    # --- Phase 1: Initial Pickup ---
    
    # Left arm picks up left_part
    # Approach sequence: left_home -> left_source -> grasp
    await robot.move(ARM_LEFT, POSE_LEFT_SOURCE)
    await robot.grasp(ARM_LEFT, OBJ_LEFT)
    
    # Right arm picks up right_part
    # Approach sequence: right_home -> right_source -> grasp
    await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE)
    await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
    
    # --- Phase 2: Right Arm Places Right Part ---
    
    # Move right_part to right_target
    await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET)
    await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_TARGET)
    
    # Right arm moves to depart
    await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART)
    
    # --- Phase 3: Left Part Inspection Loop ---
    
    # Move left_part to inspection zone
    # Approach sequence: left_wait -> inspection -> grasp
    await robot.move(ARM_LEFT, POSE_LEFT_WAIT)
    await robot.move(ARM_LEFT, POSE_INSPECTION)
    await robot.grasp(ARM_LEFT, OBJ_LEFT)
    
    # Release onto inspection
    # This triggers invalidation of 'quality' fact
    await robot.release(ARM_LEFT, OBJ_LEFT, POSE_INSPECTION)
    
    # Immediate departure (as per required order)
    await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
    
    # --- Phase 4: Inspection & Routing ---
    
    # Wait for RIGHT to inspect quality
    # Constraint: "LEFT places at inspection and immediately departs before RIGHT inspects quality."
    # Since we just departed, we can now proceed to wait/check.
    # We loop to ensure we get the observation updated by the release.
    # The task says "RIGHT issues each inspection observation".
    
    # We need to determine the target based on the quality observation.
    # "At each inspection pass use the newly issued current quality record on LEFT inspection pickup."
    
    # We will perform the logic to decide target (Target vs Rework).
    # Max 2 passes.
    
    current_pass = 0
    max_passes = 2
    
    while current_pass < max_passes:
        current_pass += 1
        
        # Get the current quality state
        # Note: inspect returns the Observation for the fact.
        quality_obs = await get_quality_obs()
        
        # Decode value: {"accept_by_pass": [true, true], "item_id": "left_part"}
        # accept_by_pass[pass_index] selects target if true, otherwise rework.
        # pass_index is 0-based.
        accept_list = quality_obs.value["accept_by_pass"]
        
        should_accept = accept_list[current_pass - 1]
        
        if should_accept:
            # Path to Target
            # Approach sequence: left_wait -> inspection -> grasp
            await robot.move(ARM_LEFT, POSE_LEFT_WAIT)
            await robot.move(ARM_LEFT, POSE_INSPECTION)
            # Use the newly issued current quality record
            await robot.grasp(ARM_LEFT, OBJ_LEFT, observation=quality_obs)
            
            await robot.move(ARM_LEFT, POSE_LEFT_TARGET)
            await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
            
            # Depart
            await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
            break # Done
        else:
            # Path to Rework
            # Approach sequence: rework_wait -> rework -> grasp
            await robot.move(ARM_LEFT, POSE_REWORK_WAIT)
            await robot.move(ARM_LEFT, POSE_REWORK)
            await robot.grasp(ARM_LEFT, OBJ_LEFT)
            
            await robot.release(ARM_LEFT, OBJ_LEFT, POSE_REWORK)
            
            # Depart (immediate separation)
            await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
            
            # Loop back to inspection
            # Move to inspection zone
            await robot.move(ARM_LEFT, POSE_LEFT_WAIT)
            await robot.move(ARM_LEFT, POSE_INSPECTION)
            await robot.grasp(ARM_LEFT, OBJ_LEFT)
            
            await robot.release(ARM_LEFT, OBJ_LEFT, POSE_INSPECTION)
            await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
            # Continue loop to check quality again
