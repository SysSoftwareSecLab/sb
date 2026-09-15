import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants derived from PUBLIC TASK
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_LEFT_WAIT = "left_wait"
    POSE_REWORK_WAIT = "rework_wait"
    POSE_REWORK = "rework"
    POSE_INSPECTION = "inspection"
    POSE_LEFT_TARGET = "left_target"
    POSE_LEFT_DEPART = "left_depart"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_TARGET = "right_target"
    POSE_RIGHT_DEPART = "right_depart"
    
    OBJ_LEFT_PART = "left_part"
    OBJ_RIGHT_PART = "right_part"
    
    FACT_QUALITY = "quality"
    
    # Initial State: LEFT at left_home, RIGHT at right_home
    # Goal: Both parts at targets, arms at departures.
    # Constraint: LEFT places at inspection and immediately departs before RIGHT inspects.
    # Constraint: Use newly issued quality record on LEFT inspection pickup.
    # Constraint: At most 2 inspection passes.
    # Logic: A accepts on first pass (index 0), B on second (index 1).
    # Since we must implement the structure and ensure success, we assume the path 
    # that leads to success (Pass 1 -> Rework -> Pass 2 -> Target) or simply 
    # follow the accept_by_pass logic. Given "A accepts on first pass, B on second",
    # and we need to reach the target, we likely need to go through the rework loop 
    # if the first pass fails, or if the task implies the "branch-path contrast".
    # However, the goal is "left part reaches acceptance within two inspection passes".
    # We will implement the loop: Inspect -> Check -> (Rework or Target).
    
    # --- Phase 1: Initial Pickup ---
    
    # LEFT moves to source and grasps left_part
    await robot.move(ARM_LEFT, POSE_LEFT_SOURCE)
    obs_init = await robot.grasp(ARM_LEFT, OBJ_LEFT_PART)
    
    # RIGHT moves to source and grasps right_part
    await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE)
    await robot.grasp(ARM_RIGHT, OBJ_RIGHT_PART)
    
    # --- Phase 2: First Inspection Cycle ---
    
    # LEFT moves to inspection wait
    await robot.move(ARM_LEFT, POSE_LEFT_WAIT)
    
    # LEFT moves to inspection and releases left_part
    # This triggers invalidation of 'quality' fact
    await robot.move(ARM_LEFT, POSE_INSPECTION)
    await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_INSPECTION)
    
    # LEFT must immediately depart to left_depart
    # "LEFT places at inspection and immediately departs before RIGHT inspects"
    await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
    
    # RIGHT can now inspect
    # RIGHT moves to inspection (approach not strictly defined for RIGHT inspecting, 
    # but move is allowed. Assuming direct move or implicit approach logic handled by runtime 
    # if not in approach_sequences. Given "SERIAL_CARRIED_PATHS_CROSS_IN_XY_PROJECTION", 
    # we move to the interaction zone).
    await robot.move(ARM_RIGHT, POSE_INSPECTION)
    
    # RIGHT inspects quality. This issues a new Observation.
    # "RIGHT issues each inspection observation."
    obs_pass1 = await robot.inspect(ARM_RIGHT, FACT_QUALITY)
    
    # --- Phase 3: Decision Logic ---
    
    # Check accept_by_pass[0]
    # Initial value: {"accept_by_pass": [true, true], ...}
    # If true, we go to target. If false, we go to rework.
    # The task description says "A accepts on first pass, B on second".
    # This implies a contrast. We will implement the logic to handle the observation.
    
    accept_first = obs_pass1.value["accept_by_pass"][0]
    
    if accept_first:
        # Path A: Accepted on first pass.
        # LEFT needs to pick up from inspection and move to target.
        # LEFT must depart from left_depart to left_wait (approach start)
        await robot.move(ARM_LEFT, POSE_LEFT_WAIT)
        
        # Approach and Grasp
        # "At each inspection pass use the newly issued current quality record on LEFT inspection pickup."
        await robot.move(ARM_LEFT, POSE_INSPECTION)
        await robot.grasp(ARM_LEFT, OBJ_LEFT_PART, observation=obs_pass1)
        
        # Move to target and release
        await robot.move(ARM_LEFT, POSE_LEFT_TARGET)
        await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_LEFT_TARGET)
        
        # Depart
        await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
    else:
        # Path B: Rejected on first pass. Go to rework.
        # LEFT moves to rework wait
        await robot.move(ARM_LEFT, POSE_REWORK_WAIT)
        
        # LEFT moves to inspection, grasps (using obs_pass1), moves to rework, releases
        await robot.move(ARM_LEFT, POSE_INSPECTION)
        await robot.grasp(ARM_LEFT, OBJ_LEFT_PART, observation=obs_pass1)
        
        await robot.move(ARM_LEFT, POSE_REWORK)
        await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_REWORK)
        
        # LEFT departs (immediate separation)
        await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
        
        # --- Phase 4: Second Inspection Cycle ---
        
        # LEFT moves to rework wait
        await robot.move(ARM_LEFT, POSE_REWORK_WAIT)
        
        # LEFT moves to rework and grasps
        # No observation required for rework pickup unless specified (not in task text)
        await robot.move(ARM_LEFT, POSE_REWORK)
        await robot.grasp(ARM_LEFT, OBJ_LEFT_PART)
        
        # LEFT moves to inspection and releases
        await robot.move(ARM_LEFT, POSE_INSPECTION)
        await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_INSPECTION)
        
        # LEFT departs immediately
        await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
        
        # RIGHT inspects again
        await robot.inspect(ARM_RIGHT, FACT_QUALITY)
        # Note: We need the observation for the final pickup.
        # The spec says "RIGHT issues each inspection observation".
        # We assume the inspect call returns the new observation.
        # However, we need to capture it.
        # Re-calling inspect to get the latest observation for the grasp.
        obs_pass2 = await robot.inspect(ARM_RIGHT, FACT_QUALITY)
        
        # --- Phase 5: Final Placement ---
        
        # LEFT moves to inspection wait
        await robot.move(ARM_LEFT, POSE_LEFT_WAIT)
        
        # LEFT moves to inspection, grasps (using obs_pass2)
        await robot.move(ARM_LEFT, POSE_INSPECTION)
        await robot.grasp(ARM_LEFT, OBJ_LEFT_PART, observation=obs_pass2)
        
        # Move to target and release
        await robot.move(ARM_LEFT, POSE_LEFT_TARGET)
        await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_LEFT_TARGET)
        
        # Depart
        await robot.move(ARM_LEFT, POSE_LEFT_DEPART)

    # --- Phase 6: Right Part Completion ---
    
    # RIGHT moves to right_target and releases right_part
    await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET)
    await robot.release(ARM_RIGHT, OBJ_RIGHT_PART, POSE_RIGHT_TARGET)
    
    # RIGHT departs to right_depart
    await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART)
