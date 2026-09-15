from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # CONCURRENCY=SERIAL, layout=L0: run the two independent attachment
    # chains one after the other (serial), not joined concurrently.
    #
    # Each chain: approach from home -> grasp -> move to target ->
    # release -> move to depart.
    #
    # Approach sequences require: start at start_pose, then the very next
    # robot call in the same coroutine at the same virtual instant must be
    # the matching grasp.

    # ---- LEFT chain ----
    await robot.move("LEFT", "left_home")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")

    # ---- RIGHT chain ----
    await robot.move("RIGHT", "right_home")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
