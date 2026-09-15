import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- Phase 1: Resource Checks (Serial) ---
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order.
    # Resources are initially OFF, so we just acquire and release.
    # Timeout is set to 1.0s (within 0-120s range).
    
    for res_id in ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]:
        await robot.acquire("LEFT", res_id, 1.0)
        await robot.release_resource("LEFT", res_id)

    # --- Phase 2: Gate Protocol (Serial) ---
    # Signal rq2_gate exactly once.
    gate_receipt = robot.signal("rq2_gate")
    
    # Wait its exact active receipt exactly once.
    # The receipt we just signaled should be active immediately.
    await robot.wait_event("rq2_gate", 1.0)
    
    # Clear exactly that version after its assigned protected scope.
    # The scope is "before starting the complete inherited dual-arm mission".
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- Phase 3: Inherited Dual-Arm Mission (Serial) ---
    # "A runs candidate LEFT then RIGHT serially"
    
    # Step 3.1: LEFT Worker
    # Both workers independently inspect allocation once before choosing their own branch.
    alloc_obs_left = await robot.inspect("LEFT", "allocation")
    
    # Determine selected arm from observation value.
    # Observation value is {"item_id": "shared_part", "selected_arm": "LEFT"}
    selected_arm = alloc_obs_left.value["selected_arm"]
    
    if selected_arm == "LEFT":
        # LEFT is selected.
        # Approach: move to shared_source (start_pose is left_home).
        await robot.move("LEFT", "shared_source")
        
        # Grasp: must carry that arm's own current allocation observation.
        await robot.grasp("LEFT", "shared_part", observation=alloc_obs_left)
        
        # Transport: move to shared_target.
        await robot.move("LEFT", "shared_target")
        
        # Release: at target (shared_target) and immediately depart.
        await robot.release("LEFT", "shared_part", "shared_target")
        await robot.move("LEFT", "left_depart")
    else:
        # LEFT is unselected. Makes no move/grasp/release call.
        # Stays at left_home (initial pose).
        pass

    # Step 3.2: RIGHT Worker
    # Both workers independently inspect allocation once.
    # Note: The allocation fact is not invalidated by release in this task spec.
    alloc_obs_right = await robot.inspect("RIGHT", "allocation")
    
    # Determine selected arm.
    # Since LEFT already acted (or not) based on the immutable allocation, 
    # RIGHT will see the same selected_arm.
    selected_arm_right = alloc_obs_right.value["selected_arm"]
    
    if selected_arm_right == "RIGHT":
        # RIGHT is selected.
        # Approach: move to shared_source (start_pose is right_home).
        await robot.move("RIGHT", "shared_source")
        
        # Grasp: must carry that arm's own current allocation observation.
        await robot.grasp("RIGHT", "shared_part", observation=alloc_obs_right)
        
        # Transport: move to shared_target.
        await robot.move("RIGHT", "shared_target")
        
        # Release: at target and immediately depart.
        await robot.release("RIGHT", "shared_part", "shared_target")
        await robot.move("RIGHT", "right_depart")
    else:
        # RIGHT is unselected. Makes no move/grasp/release call.
        # Stays at right_home (initial pose).
        pass
