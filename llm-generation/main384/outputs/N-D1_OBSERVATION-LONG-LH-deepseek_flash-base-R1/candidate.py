from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # ---- LEFT: approach left_source from left_home, grasp left_part ----
    await robot.move("LEFT", "left_source")
    left_obs = await robot.grasp("LEFT", "left_part")

    # ---- LEFT: carry left_part to inspection and release ----
    await robot.move("LEFT", "inspection")
    await robot.release("LEFT", "left_part", "inspection")
    # immediate separating departure
    await robot.move("LEFT", "left_wait")

    # ---- RIGHT: approach right_source from right_home, grasp right_part ----
    await robot.move("RIGHT", "right_source")
    right_obs = await robot.grasp("RIGHT", "right_part")

    # ---- RIGHT: carry right_part to right_target and release ----
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")

    # ---- Pass 1: RIGHT inspects quality (issues current observation) ----
    quality_obs = await robot.inspect("RIGHT", "quality")

    # ---- LEFT: approach inspection from left_wait, grasp left_part ----
    await robot.move("LEFT", "inspection")
    left_obs = await robot.grasp("LEFT", "left_part", observation=quality_obs)

    # ---- LEFT: carry to rework and release (pass 1 rework) ----
    await robot.move("LEFT", "rework")
    await robot.release("LEFT", "left_part", "rework")
    await robot.move("LEFT", "rework_wait")

    # ---- Pass 2: RIGHT inspects quality again (new current observation) ----
    quality_obs = await robot.inspect("RIGHT", "quality")

    # ---- LEFT: approach rework from rework_wait, grasp left_part ----
    await robot.move("LEFT", "rework")
    left_obs = await robot.grasp("LEFT", "left_part", observation=quality_obs)

    # ---- LEFT: carry to left_target and release ----
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")
