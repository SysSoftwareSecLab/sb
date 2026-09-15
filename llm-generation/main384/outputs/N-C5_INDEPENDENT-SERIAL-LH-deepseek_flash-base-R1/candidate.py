from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # SERIAL structure: run the two independent attachment chains one after the other.
    # Each chain: approach (move to start_pose) -> grasp -> move to target -> release -> depart.
    # Approach sequences require: start at start_pose, then immediately grasp in the same coroutine.

    # ---- LEFT chain ----
    # Approach: must start at left_home, then immediately grasp left_part.
    await robot.move("LEFT", "left_home")
    await robot.grasp("LEFT", "left_part")

    # Transport to left_target.
    await robot.move("LEFT", "left_target")

    # Release at left_target (a logical support), then immediately depart.
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")

    # ---- RIGHT chain ----
    # Approach: must start at right_home, then immediately grasp right_part.
    await robot.move("RIGHT", "right_home")
    await robot.grasp("RIGHT", "right_part")

    # Transport to right_target.
    await robot.move("RIGHT", "right_target")

    # Release at right_target (a logical support), then immediately depart.
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
