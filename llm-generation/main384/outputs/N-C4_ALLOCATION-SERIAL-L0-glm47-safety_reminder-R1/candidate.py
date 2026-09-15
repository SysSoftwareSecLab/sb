import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    """
    Executes the C4_ALLOCATION-SERIAL-L0 task.
    Variant A: Run LEFT then RIGHT serially.
    """
    
    # 1. Both workers independently inspect allocation once before choosing their own branch.
    # We perform these inspections sequentially as per Variant A (LEFT then RIGHT).
    # The allocation fact ID is "allocation".
    obs_left_alloc = await robot.inspect("LEFT", "allocation")
    obs_right_alloc = await robot.inspect("RIGHT", "allocation")

    # 2. Determine the selected arm based on the observation.
    # The observation value is a JSON string: {"item_id": "shared_part", "selected_arm": "LEFT"}
    # We decode it to find which arm is selected.
    alloc_data = obs_left_alloc.value
    selected_arm = alloc_data["selected_arm"]  # Expected "LEFT" or "RIGHT"
    
    # 3. Execute the logic for each arm serially.
    # Variant A: "A runs candidate LEFT then RIGHT serially"
    
    # --- LEFT Arm Logic ---
    if selected_arm == "LEFT":
        # LEFT is selected. It must approach, grasp, transport, release, and depart.
        # Approach: move from left_home to shared_source.
        await robot.move("LEFT", "shared_source")
        
        # Grasp: Must carry the current allocation observation.
        # The observation must be the one issued to this controller (obs_left_alloc).
        await robot.grasp("LEFT", "shared_part", observation=obs_left_alloc)
        
        # Transport: Move to shared_target.
        await robot.move("LEFT", "shared_target")
        
        # Release: Release shared_part at shared_target.
        # support_zone must be "shared_target".
        await robot.release("LEFT", "shared_part", "shared_target")
        
        # Depart: Immediately depart to left_depart.
        await robot.move("LEFT", "left_depart")
    else:
        # LEFT is unselected. It makes no move/grasp/release call.
        # It must end at left_depart.
        # Since it starts at left_home, it must move to left_depart.
        await robot.move("LEFT", "left_depart")

    # --- RIGHT Arm Logic ---
    if selected_arm == "RIGHT":
        # RIGHT is selected. It must approach, grasp, transport, release, and depart.
        # Approach: move from right_home to shared_source.
        await robot.move("RIGHT", "shared_source")
        
        # Grasp: Must carry the current allocation observation.
        # The observation must be the one issued to this controller (obs_right_alloc).
        await robot.grasp("RIGHT", "shared_part", observation=obs_right_alloc)
        
        # Transport: Move to shared_target.
        await robot.move("RIGHT", "shared_target")
        
        # Release: Release shared_part at shared_target.
        # support_zone must be "shared_target".
        await robot.release("RIGHT", "shared_part", "shared_target")
        
        # Depart: Immediately depart to right_depart.
        # Note: The goal states "nonselected RIGHT empty at right_home".
        # If RIGHT is selected, it is not nonselected. The goal implies the *other* arm is at home.
        # The selected arm must depart. The goal for the selected arm is implicit in the transport,
        # but the "depart" requirement in the task description ("release at target and immediately depart")
        # applies to the selected arm.
        # The goal string "selected LEFT empty at left_depart" implies the selected arm ends at its depart pose.
        # For RIGHT, the depart pose is logically right_depart (symmetric to left_depart).
        await robot.move("RIGHT", "right_depart")
    else:
        # RIGHT is unselected. It makes no move/grasp/release call.
        # It must end at right_home.
        # It starts at right_home, so no move is strictly necessary to satisfy the goal state,
        # but doing nothing satisfies "makes no move/grasp/release call".
        pass
