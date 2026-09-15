import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # 1. Both workers independently inspect allocation once
    # Serial execution: LEFT then RIGHT
    alloc_obs_left: Observation = await robot.inspect("LEFT", "allocation")
    alloc_obs_right: Observation = await robot.inspect("RIGHT", "allocation")

    # Determine selected arm from LEFT's observation
    # Value: {"item_id": "shared_part", "selected_arm": "LEFT"}
    selected_arm = alloc_obs_left.value["selected_arm"]
    unselected_arm = "RIGHT" if selected_arm == "LEFT" else "LEFT"

    # 2. Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    # This is a prerequisite for signalling the gate.
    gap_ids = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    for rid in gap_ids:
        await robot.acquire("LEFT", rid, timeout_s=4.0)
        await robot.release_resource("LEFT", rid)

    # 3. Signal rq2_gate exactly once
    gate_receipt: EventReceipt = robot.signal("rq2_gate")

    # 4. Wait for rq2_gate exactly once
    # The wait must happen immediately after the signal as per required_order.
    # The gate must remain active during the subsequent mission.
    active_gate_receipt: EventReceipt = await robot.wait_event("rq2_gate", timeout_s=4.0)

    # 5. Execute the inherited dual-arm mission (Serial: LEFT then RIGHT)
    # The selected arm performs the transport; the unselected arm remains at home.
    
    # Sequence for the selected arm:
    # - Move to start_pose (home)
    # - Move to interaction_pose (shared_source)
    # - Grasp (carrying its own allocation observation)
    # - Move to target (shared_target)
    # - Release
    # - Depart (move to depart pose)
    
    if selected_arm == "LEFT":
        # LEFT is selected
        # LEFT: Home -> Source -> Grasp -> Target -> Release -> Depart
        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "shared_source")
        await robot.grasp("LEFT", "shared_part", observation=alloc_obs_left)
        await robot.move("LEFT", "shared_target")
        await robot.release("LEFT", "shared_part", "shared_target")
        await robot.move("LEFT", "left_depart")

        # RIGHT is unselected
        # RIGHT: Stay at home (already there, but ensure state)
        await robot.move("RIGHT", "right_home")
    else:
        # RIGHT is selected
        # LEFT is unselected
        # LEFT: Stay at home
        await robot.move("LEFT", "left_home")

        # RIGHT: Home -> Source -> Grasp -> Target -> Release -> Depart
        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", "shared_source")
        await robot.grasp("RIGHT", "shared_part", observation=alloc_obs_right)
        await robot.move("RIGHT", "shared_target")
        await robot.release("RIGHT", "shared_part", "shared_target")
        await robot.move("RIGHT", "right_depart")

    # 6. Clear rq2_gate exactly that version after the mission
    robot.clear_event("rq2_gate", expected_version=active_gate_receipt.version)
