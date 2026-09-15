import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # 1. Both workers independently inspect allocation once before choosing their own branch.
    # We run these inspections concurrently as allowed by "Both workers independently inspect".
    alloc_obs_left: Observation = await robot.inspect("LEFT", "allocation")
    alloc_obs_right: Observation = await robot.inspect("RIGHT", "allocation")

    # Determine selected arm from the observation value.
    # The value is {"item_id": "shared_part", "selected_arm": "LEFT"}
    selected_arm = alloc_obs_left.value["selected_arm"]
    unselected_arm = "RIGHT" if selected_arm == "LEFT" else "LEFT"

    # 2. Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order.
    # This is a prerequisite for signalling the gate.
    gap_resources = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    for res_id in gap_resources:
        await robot.acquire("LEFT", res_id, timeout_s=4.0)
        await robot.release_resource("LEFT", res_id)

    # 3. Signal rq2_gate exactly once, wait its exact active receipt exactly once.
    # "wait immediately after the signal".
    gate_receipt: EventReceipt = robot.signal("rq2_gate")
    wait_receipt: EventReceipt = await robot.wait_event("rq2_gate", timeout_s=4.0)

    # 4. Keep rq2_gate active while executing the complete inherited dual-arm mission.
    # The mission: Selected arm transports shared_part from shared_source to shared_target.
    # Unselected arm remains at home.
    # "A runs candidate LEFT then RIGHT serially" -> We execute the mission logic serially.
    
    # Selected Arm Path:
    # Move to start_pose for approach (left_home or right_home).
    # Approach sequence: move to interaction_pose (shared_source) -> grasp.
    # Transport: move to shared_target -> release -> depart.
    
    # Unselected Arm Path:
    # Remains at home (initial pose). No move/grasp/release calls.

    # Selected Arm Sequence
    # Initial pose is already home, so we can start approach.
    # Approach: Move to shared_source
    await robot.move(selected_arm, "shared_source", timeout_s=4.0)
    
    # Grasp: Must carry the arm's own current allocation observation.
    # We use alloc_obs_left or alloc_obs_right depending on which arm is selected.
    grasp_obs = alloc_obs_left if selected_arm == "LEFT" else alloc_obs_right
    await robot.grasp(selected_arm, "shared_part", observation=grasp_obs)
    
    # Transport: Move to shared_target
    await robot.move(selected_arm, "shared_target", timeout_s=4.0)
    
    # Release: At shared_target, support_zone is "shared_target".
    await robot.release(selected_arm, "shared_part", "shared_target")
    
    # Depart: Immediate separating departure.
    # Goal for selected arm is left_depart/right_depart.
    depart_pose = "left_depart" if selected_arm == "LEFT" else "right_depart"
    await robot.move(selected_arm, depart_pose, timeout_s=4.0)

    # Unselected Arm Sequence
    # "The unselected arm makes no move/grasp/release call."
    # It is already at its goal (right_home/left_home).
    # No actions needed.

    # 5. Clear rq2_gate exactly that version after its assigned protected scope.
    # The scope was the mission execution.
    robot.clear_event("rq2_gate", expected_version=wait_receipt.version)
