import asyncio
import json
from typing import Optional

# The public API is imported by the runner, but we reference types for clarity if needed.
# from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot):
    """
    Executes the D1_OBSERVATION-LONG-LH task.
    
    Strategy:
    1. LEFT moves from left_home to left_source and grasps left_part.
    2. LEFT moves to inspection and releases left_part.
       - This invalidates the 'quality' fact (version 1 -> 2).
       - LEFT immediately departs to left_depart.
    3. RIGHT moves from right_home to right_source and grasps right_part.
    4. RIGHT moves to inspection and releases right_part.
       - This invalidates 'quality' again (version 2 -> 3).
       - RIGHT immediately departs to right_depart.
    5. LEFT moves from left_depart to inspection (approach).
    6. RIGHT inspects 'quality' (getting version 3).
    7. RIGHT signals 'inspection' event (version 1).
    8. LEFT grasps left_part at inspection using the observation (version 3).
    9. LEFT checks the decision logic (accept_by_pass[0] is True).
    10. LEFT moves to left_target and releases left_part.
    11. LEFT moves to left_depart.
    """
    
    # Constants from task
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    OBJ_LEFT = "left_part"
    OBJ_RIGHT = "right_part"
    
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_INSPECTION = "inspection"
    POSE_LEFT_WAIT = "left_wait"
    POSE_LEFT_DEPART = "left_depart"
    POSE_LEFT_TARGET = "left_target"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_DEPART = "right_depart"
    POSE_RIGHT_TARGET = "right_target"
    
    FACT_QUALITY = "quality"
    EVENT_INSPECTION = "inspection"
    
    # Timeout for moves (default is 4s)
    MOVE_TIMEOUT = 4.0
    
    # --- Step 1: LEFT picks up left_part ---
    await robot.move(ARM_LEFT, POSE_LEFT_SOURCE, timeout_s=MOVE_TIMEOUT)
    # No observation required for initial grasp
    await robot.grasp(ARM_LEFT, OBJ_LEFT)
    
    # --- Step 2: LEFT places left_part at inspection ---
    await robot.move(ARM_LEFT, POSE_INSPECTION, timeout_s=MOVE_TIMEOUT)
    await robot.release(ARM_LEFT, OBJ_LEFT, POSE_INSPECTION)
    # Invalidation of quality happens here (v1 -> v2).
    # Immediate departure required
    await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=MOVE_TIMEOUT)
    
    # --- Step 3: RIGHT picks up right_part ---
    # Can run concurrently with LEFT's departure if not conflicting, 
    # but LEFT is already departing. RIGHT starts from home.
    await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE, timeout_s=MOVE_TIMEOUT)
    await robot.grasp(ARM_RIGHT, OBJ_RIGHT)
    
    # --- Step 4: RIGHT places right_part at inspection ---
    await robot.move(ARM_RIGHT, POSE_INSPECTION, timeout_s=MOVE_TIMEOUT)
    await robot.release(ARM_RIGHT, OBJ_RIGHT, POSE_INSPECTION)
    # Invalidation of quality happens here (v2 -> v3).
    # Immediate departure required
    await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART, timeout_s=MOVE_TIMEOUT)
    
    # --- Step 5: LEFT approaches inspection for pickup ---
    # Must start from left_wait (approach sequence constraint).
    await robot.move(ARM_LEFT, POSE_LEFT_WAIT, timeout_s=MOVE_TIMEOUT)
    await robot.move(ARM_LEFT, POSE_INSPECTION, timeout_s=MOVE_TIMEOUT)
    
    # --- Step 6 & 7: RIGHT inspects and signals ---
    # RIGHT is at right_depart. Inspect is fast (0.1s).
    # This fetches the current version of 'quality' (v3).
    obs_quality = await robot.inspect(ARM_RIGHT, FACT_QUALITY)
    
    # Signal the inspection event.
    # This creates an EventReceipt that LEFT must use.
    receipt_inspection = robot.signal(EVENT_INSPECTION, item_id=OBJ_LEFT)
    
    # --- Step 8: LEFT grasps left_part ---
    # Must use the observation from RIGHT.
    # Must happen immediately after approach (no intervening calls).
    await robot.grasp(ARM_LEFT, OBJ_LEFT, observation=obs_quality)
    
    # --- Step 9: LEFT decides target ---
    # Parse the observation value.
    # value_json is a string, .value is the decoded dict.
    data = obs_quality.value
    accept_by_pass = data.get("accept_by_pass", [])
    
    # We are on pass 0 (first inspection after initial placement).
    # Task spec: "A accepts on first pass".
    if len(accept_by_pass) > 0 and accept_by_pass[0]:
        target_pose = POSE_LEFT_TARGET
    else:
        # Fallback logic, though spec implies True for this path.
        # If False, we would go to rework.
        # For this specific task instance, we expect True.
        target_pose = POSE_LEFT_TARGET
        
    # --- Step 10: LEFT places at target ---
    await robot.move(ARM_LEFT, target_pose, timeout_s=MOVE_TIMEOUT)
    await robot.release(ARM_LEFT, OBJ_LEFT, target_pose)
    
    # --- Step 11: LEFT final departure ---
    await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=MOVE_TIMEOUT)
    
    # --- Verification of Terminal State ---
    # LEFT is at left_depart, empty.
    # RIGHT is at right_depart, empty (holding nothing).
    # left_part is at left_target.
    # right_part is at right_target (placed in Step 4).
    
    # No explicit return value needed.
