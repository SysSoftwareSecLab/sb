import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    """
    Task C4_ALLOCATION-SERIAL-L0 Variant A.
    Structure: Serial execution of LEFT then RIGHT.
    Goal: Transport shared_part to shared_target using the arm selected by the allocation fact.
    """

    # Constants from PUBLIC TASK
    ALLOCATION_FACT_ID = "allocation"
    OBJECT_ID = "shared_part"
    POSE_SHARED_SOURCE = "shared_source"
    POSE_SHARED_TARGET = "shared_target"
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_DEPART = "left_depart"
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_DEPART = "right_depart"
    
    # Timeout for move operations (within explicit range)
    MOVE_TIMEOUT = 4.0

    async def worker(arm: str, home_pose: str, depart_pose: str):
        """
        Worker coroutine for a specific arm.
        Inspects allocation, and if selected, performs the transport.
        """
        # 1. Inspect allocation
        # "Both workers independently inspect allocation once before choosing their own branch."
        obs: Observation = await robot.inspect(arm, ALLOCATION_FACT_ID)
        
        # Decode allocation value
        allocation_data = obs.value
        selected_arm = allocation_data.get("selected_arm")
        
        # 2. Check if this arm is selected
        if selected_arm == arm:
            # This arm is the selected worker.
            
            # 3. Approach the object
            # "Only the arm named by the current controller-issued allocation may propose shared_source approach"
            # Approach sequence requires starting from home_pose.
            await robot.move(arm, POSE_SHARED_SOURCE, timeout_s=MOVE_TIMEOUT)
            
            # 4. Grasp the object
            # "The selected grasp must carry that arm's own current allocation observation"
            # "required_next_robot_call": "grasp" (immediate call after approach)
            await robot.grasp(arm, OBJECT_ID, observation=obs)
            
            # 5. Transport to target
            await robot.move(arm, POSE_SHARED_TARGET, timeout_s=MOVE_TIMEOUT)
            
            # 6. Release the object
            # "release at target and immediately depart"
            await robot.release(arm, OBJECT_ID, POSE_SHARED_TARGET)
            
            # 7. Immediate departure
            await robot.move(arm, depart_pose, timeout_s=MOVE_TIMEOUT)
        else:
            # The unselected arm makes no move/grasp/release call.
            # It remains at home (initial pose).
            pass

    # Variant A: "A runs candidate LEFT then RIGHT serially"
    # We execute the workers sequentially.
    
    # Run LEFT worker
    await worker("LEFT", POSE_LEFT_HOME, POSE_LEFT_DEPART)
    
    # Run RIGHT worker
    await worker("RIGHT", POSE_RIGHT_HOME, POSE_RIGHT_DEPART)
