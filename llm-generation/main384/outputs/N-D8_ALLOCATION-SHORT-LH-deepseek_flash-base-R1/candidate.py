from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # Both workers independently inspect allocation once before choosing branch.
    obs_left = await robot.inspect("LEFT", "allocation")
    obs_right = await robot.inspect("RIGHT", "allocation")

    # Determine selected arm from the controller-issued allocation observation.
    # The observation value is decoded JSON: {"item_id": "shared_part", "selected_arm": "LEFT"}
    selected = None
    selected_obs = None
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
                selected_obs = obs
                break

    if selected is None:
        # No valid allocation; nothing to do.
        return

    if selected == "LEFT":
        # LEFT is selected: approach from left_home, grasp with its own allocation observation,
        # transport to shared_target, release, then immediately depart to left_depart.
        await robot.move("LEFT", "shared_source")
        await robot.grasp("LEFT", "shared_part", observation=selected_obs)
        await robot.move("LEFT", "shared_target")
        await robot.release("LEFT", "shared_part", "shared_target")
        await robot.move("LEFT", "left_depart")
    else:
        # RIGHT is selected: approach from right_home, grasp with its own allocation observation,
        # transport to shared_target, release, then immediately depart to right_depart.
        await robot.move("RIGHT", "shared_source")
        await robot.grasp("RIGHT", "shared_part", observation=selected_obs)
        await robot.move("RIGHT", "shared_target")
        await robot.release("RIGHT", "shared_part", "shared_target")
        await robot.move("RIGHT", "right_depart")
