import asyncio
import json
from typing import Optional

# The module bridge_robot_api is assumed to be available in the environment
# with the exports: Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault

async def run_task(robot):
    """
    Executes the D1_OBSERVATION-LONG-L0 task.
    
    Strategy:
    1. RIGHT moves to right_source, grasps right_part, moves to right_target, releases it, moves to right_depart.
    2. LEFT moves to left_source, grasps left_part, moves to inspection, releases it (invalidates quality).
    3. RIGHT inspects quality (generates new observation).
    4. LEFT picks up from inspection (using new observation), checks accept_by_pass.
       - If accepted: moves to left_target, releases, moves to left_depart.
       - If rejected: moves to rework, releases, moves to rework_wait, moves to rework, grasps, moves to inspection, releases.
         RIGHT inspects again. LEFT picks up, checks accept (must be true), moves to left_target, releases, moves to left_depart.
    """
    
    # Constants from task
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    OBJ_LEFT = "left_part"
    OBJ_RIGHT = "right_part"
    
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_LEFT_WAIT = "left_wait"
    POSE_INSPECTION = "inspection"
    POSE_REWORK_WAIT = "rework_wait"
    POSE_REWORK = "rework"
    POSE_LEFT_TARGET = "left_target"
    POSE_LEFT_DEPART = "left_depart"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_TARGET = "right_target"
    POSE_RIGHT_DEPART = "right_depart"
    
    FACT_QUALITY = "quality"
    
    # Helper to parse observation value
    def get_quality_value(obs: Optional['Observation']):
        if obs is None:
            return None
        return obs.value

    # --- RIGHT ARM TASK ---
    async def run_right():
        # 1. Move to source
        await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE)
        
        # 2. Grasp right_part
        await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
        
        # 3. Move to target
        await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET)
        
        # 4. Release right_part
        await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_TARGET)
        
        # 5. Move to depart
        await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART)
        
        # 6. Inspect quality (First time)
        # This generates the observation for the first inspection pass
        await robot.inspect(ARM_RIGHT, FACT_QUALITY)
        
        # 7. Inspect quality (Second time)
        # This generates the observation for the second inspection pass (if needed)
        # We perform this unconditionally to satisfy the "branch-path contrast" requirement
        # where the structure is fixed, even if the logic might not strictly need it for the 'A' branch.
        await robot.inspect(ARM_RIGHT, FACT_QUALITY)

    # --- LEFT ARM TASK ---
    async def run_left():
        # 1. Move to source
        await robot.move(ARM_LEFT, POSE_LEFT_SOURCE)
        
        # 2. Grasp left_part
        await robot.grasp(ARM_LEFT, OBJ_LEFT)
        
        # 3. Move to inspection
        await robot.move(ARM_LEFT, POSE_INSPECTION)
        
        # 4. Release left_part (First placement)
        # This invalidates the initial quality fact (version 1 -> 2)
        await robot.release(ARM_LEFT, OBJ_LEFT, POSE_INSPECTION)
        
        # --- PASS 1 ---
        
        # 5. Move to wait (approach start for inspection pickup)
        await robot.move(ARM_LEFT, POSE_LEFT_WAIT)
        
        # 6. Move to inspection (approach)
        await robot.move(ARM_LEFT, POSE_INSPECTION)
        
        # 7. Grasp left_part (Pickup 1)
        # We must use the observation issued by the first RIGHT inspect.
        # Since we don't have a shared variable, we rely on the fact that 
        # grasp consumes the *current* valid observation for the object.
        obs_1 = await robot.grasp(ARM_LEFT, OBJ_LEFT)
        
        # 8. Check logic
        val_1 = get_quality_value(obs_1)
        # Default to False if parsing fails, though spec implies valid JSON
        accept_1 = False
        if isinstance(val_1, dict) and "accept_by_pass" in val_1:
            passes = val_1["accept_by_pass"]
            if isinstance(passes, list) and len(passes) > 0:
                accept_1 = bool(passes[0])
        
        if accept_1:
            # Branch A: Accepted on first pass
            # Move to target and release
            await robot.move(ARM_LEFT, POSE_LEFT_TARGET)
            await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
            await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
        else:
            # Branch B: Rejected on first pass -> Rework
            # Move to rework
            await robot.move(ARM_LEFT, POSE_REWORK)
            await robot.release(ARM_LEFT, OBJ_LEFT, POSE_REWORK)
            
            # Move to wait (approach start for rework pickup)
            await robot.move(ARM_LEFT, POSE_REWORK_WAIT)
            
            # Move to rework (approach)
            await robot.move(ARM_LEFT, POSE_REWORK)
            
            # Grasp left_part (Pickup from rework)
            await robot.grasp(ARM_LEFT, OBJ_LEFT)
            
            # Move to inspection
            await robot.move(ARM_LEFT, POSE_INSPECTION)
            
            # Release left_part (Second placement)
            # This invalidates quality fact (version 2 -> 3)
            await robot.release(ARM_LEFT, OBJ_LEFT, POSE_INSPECTION)
            
            # --- PASS 2 ---
            
            # Move to wait (approach start for inspection pickup)
            await robot.move(ARM_LEFT, POSE_LEFT_WAIT)
            
            # Move to inspection (approach)
            await robot.move(ARM_LEFT, POSE_INSPECTION)
            
            # Grasp left_part (Pickup 2)
            # Uses observation from second RIGHT inspect
            obs_2 = await robot.grasp(ARM_LEFT, OBJ_LEFT)
            
            # Check logic (Must be accepted)
            val_2 = get_quality_value(obs_2)
            accept_2 = False
            if isinstance(val_2, dict) and "accept_by_pass" in val_2:
                passes = val_2["accept_by_pass"]
                if isinstance(passes, list) and len(passes) > 1:
                    accept_2 = bool(passes[1])
            
            # Move to target and release
            await robot.move(ARM_LEFT, POSE_LEFT_TARGET)
            await robot.release(ARM_LEFT, OBJ_LEFT, POSE_LEFT_TARGET)
            await robot.move(ARM_LEFT, POSE_LEFT_DEPART)

    # Run both arms concurrently
    await asyncio.gather(run_left(), run_right())
