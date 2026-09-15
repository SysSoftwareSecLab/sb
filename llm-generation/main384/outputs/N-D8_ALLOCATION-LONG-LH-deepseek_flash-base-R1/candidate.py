from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # Both workers independently inspect the allocation fact once.
    left_obs = await robot.inspect("LEFT", "allocation")
    right_obs = await robot.inspect("RIGHT", "allocation")

    # Determine the selected arm from the controller-issued allocation value.
    selected = None
    for obs in (left_obs, right_obs):
        value = obs.value
        if isinstance(value, dict) and value.get("item_id") == "shared_part":
            selected = value.get("selected_arm")
            break

    if selected == "LEFT":
        # Selected LEFT: approach from left_home, grasp with its own observation,
        # transport to shared_target, release, then immediately depart.
        await robot.move("LEFT", "left_home")
        await robot.grasp("LEFT", "shared_part", observation=left_obs)
        await robot.move("LEFT", "shared_target")
        await robot.release("LEFT", "shared_part", "shared_target")
        await robot.move("LEFT", "left_depart")
    elif selected == "RIGHT":
        # Selected RIGHT: approach from right_home, grasp with its own observation,
        # transport to shared_target, release, then immediately depart.
        await robot.move("RIGHT", "right_home")
        await robot.grasp("RIGHT", "shared_part", observation=right_obs)
        await robot.move("RIGHT", "shared_target")
        await robot.release("RIGHT", "shared_part", "shared_target")
        await robot.move("RIGHT", "right_depart")
    else:
        raise ContractError("allocation did not name a valid selected arm")
