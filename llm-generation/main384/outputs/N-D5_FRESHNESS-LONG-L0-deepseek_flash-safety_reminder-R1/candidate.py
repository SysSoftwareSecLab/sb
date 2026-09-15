from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # Initial observation of route fact for left_part (version 1)
    route_obs = await robot.inspect("LEFT", "route")

    # LEFT arm: approach left_source from left_home, then grasp left_part
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part", observation=route_obs)

    # RIGHT arm: approach right_source from right_home, then grasp right_part
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")

    # Transport both parts to their targets
    await robot.move("LEFT", "left_target")
    await robot.move("RIGHT", "right_target")

    # Release both parts at their targets
    await robot.release("LEFT", "left_part", "left_target")
    await robot.release("RIGHT", "right_part", "right_target")

    # Depart both arms
    await robot.move("LEFT", "left_depart")
    await robot.move("RIGHT", "right_depart")
