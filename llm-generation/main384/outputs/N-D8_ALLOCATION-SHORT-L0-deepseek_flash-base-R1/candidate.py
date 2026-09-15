from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # Both workers independently inspect allocation once before choosing their own branch.
    obs_left = await robot.inspect("LEFT", "allocation")
    obs_right = await robot.inspect("RIGHT", "allocation")

    # Determine selected arm from the current controller-issued allocation observation.
    # The allocation fact value is {"item_id": "shared_part", "selected_arm": "LEFT"}.
    selected = None
    for obs in (obs_left, obs_right):
        try:
            val = obs.value
        except Exception:
            val = None
        if isinstance(val, dict):
            arm = val.get("selected_arm")
            item = val.get("item_id")
            if item == "shared_part" and arm in ("LEFT", "RIGHT"):
                selected = arm
                break

    if selected is None:
        # Fallback: use the LEFT observation's decoded value if available.
        try:
            val = obs_left.value
            if isinstance(val, dict):
                selected = val.get("selected_arm")
        except Exception:
            selected = None

    if selected not in ("LEFT", "RIGHT"):
        selected = "LEFT"

    # The selected arm's own current allocation observation must be carried into grasp.
    if selected == "LEFT":
        selected_obs = obs_left
        selected_arm = "LEFT"
        start_pose = "left_home"
        goal_pose = "left_depart"
    else:
        selected_obs = obs_right
        selected_arm = "RIGHT"
        start_pose = "right_home"
        goal_pose = "right_depart"

    # Only the selected arm may propose shared_source approach, shared_part grasp,
    # or carried transport. The unselected arm makes no move/grasp/release call.
    #
    # Approach must start from the declared start_pose, and the same candidate
    # coroutine must immediately call grasp at the same virtual time with no
    # intervening robot call.
    await robot.move(selected_arm, start_pose)
    await robot.grasp(selected_arm, "shared_part", observation=selected_obs)

    # Carried transport to shared_target.
    await robot.move(selected_arm, "shared_target")

    # Release at target and immediately depart.
    await robot.release(selected_arm, "shared_part", "shared_target")
    await robot.move(selected_arm, goal_pose)
