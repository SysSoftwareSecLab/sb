import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # 1. Both workers independently inspect allocation once before choosing their own branch.
    # We perform these inspections concurrently.
    inspect_left_task = asyncio.create_task(robot.inspect("LEFT", "allocation"))
    inspect_right_task = asyncio.create_task(robot.inspect("RIGHT", "allocation"))

    # Await results
    obs_left: Observation = await inspect_left_task
    obs_right: Observation = await inspect_right_task

    # Determine the selected arm from the observation value
    # The value is {"item_id": "shared_part", "selected_arm": "LEFT"}
    selected_arm = obs_left.value["selected_arm"]
    unselected_arm = "RIGHT" if selected_arm == "LEFT" else "LEFT"

    # 2. Only the arm named by the current controller-issued allocation may propose...
    # The unselected arm makes no move/grasp/release call.
    # The selected arm must perform the transport.
    
    # Identify the correct observation to carry during grasp
    # "The selected grasp must carry that arm's own current allocation observation"
    if selected_arm == "LEFT":
        grasp_obs = obs_left
    else:
        grasp_obs = obs_right

    # 3. Selected arm sequence: Approach -> Grasp -> Transport -> Release -> Depart
    # Approach: move from home to shared_source
    # Note: The task requires immediate grasp after approach.
    await robot.move(selected_arm, "shared_source")
    
    # Grasp: Must carry the observation
    await robot.grasp(selected_arm, "shared_part", observation=grasp_obs)
    
    # Transport: Move to shared_target
    await robot.move(selected_arm, "shared_target")
    
    # Release: At shared_target, support_zone is "shared_target"
    await robot.release(selected_arm, "shared_part", "shared_target")
    
    # Depart: Move to depart pose (left_depart or right_depart)
    # The goal requires the selected arm to end at its depart pose.
    depart_pose = "left_depart" if selected_arm == "LEFT" else "right_depart"
    await robot.move(selected_arm, depart_pose)

    # The unselected arm remains at its home pose (right_home or left_home),
    # satisfying the goal condition "nonselected RIGHT empty at right_home" (or LEFT).
    # No further action needed.
