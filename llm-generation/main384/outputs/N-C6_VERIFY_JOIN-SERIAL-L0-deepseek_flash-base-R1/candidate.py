from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # SERIAL structure: run the two verifier branches one after another,
    # then join on both ready events before the single payload consumer.
    #
    # Branch LEFT: approach left_part from left_home, grasp, inspect
    # left_verification, signal left_ready.
    # Branch RIGHT: approach right_part from right_home, grasp, inspect
    # right_verification, signal right_ready.
    # Join: wait for both left_ready and right_ready.
    # Consumer: move both parts to their targets, release, depart.

    # ---- LEFT verifier branch ----
    await robot.move("LEFT", "left_home")
    await robot.move("LEFT", "left_source")
    left_obs = await robot.grasp("LEFT", "left_part")
    await robot.inspect("LEFT", "left_verification")
    left_ready_receipt = robot.signal("left_ready", "left_part")

    # ---- RIGHT verifier branch ----
    await robot.move("RIGHT", "right_home")
    await robot.move("RIGHT", "right_source")
    right_obs = await robot.grasp("RIGHT", "right_part")
    await robot.inspect("RIGHT", "right_verification")
    right_ready_receipt = robot.signal("right_ready", "right_part")

    # ---- Join on both ready events ----
    left_evt = await robot.wait_event("left_ready", 5.0)
    right_evt = await robot.wait_event("right_ready", 5.0)

    # Clear the events after the join, using the versions from the receipts.
    robot.clear_event("left_ready", expected_version=left_evt.version)
    robot.clear_event("right_ready", expected_version=right_evt.version)

    # ---- Single payload consumer ----
    # Transport left_part to left_target and release.
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")

    # Transport right_part to right_target and release.
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
