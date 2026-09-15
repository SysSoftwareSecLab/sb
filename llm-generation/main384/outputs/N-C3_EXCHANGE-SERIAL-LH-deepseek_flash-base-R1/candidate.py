from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # Variant A: SERIAL structure.
    # Each arm deposits its own part on its own pad, clears the pad,
    # publishes its own item-bound ready event, waits for peer ready,
    # then consumes the peer item and carries it to its own target.

    # --- LEFT arm: deposit left_part on left_pad, clear, signal left_ready ---
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_pad")
    await robot.release("LEFT", "left_part", "left_pad")
    await robot.move("LEFT", "left_clear")
    left_ready = robot.signal("left_ready", "left_part")

    # --- RIGHT arm: deposit right_part on right_pad, clear, signal right_ready ---
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_pad")
    await robot.release("RIGHT", "right_part", "right_pad")
    await robot.move("RIGHT", "right_clear")
    right_ready = robot.signal("right_ready", "right_part")

    # --- LEFT consumes RIGHT's part ---
    left_receipt = await robot.wait_event("right_ready", 4)
    await robot.move("LEFT", "left_pickup_wait")
    await robot.grasp("LEFT", "right_part")
    await robot.move("LEFT", "left_target", receipt=left_receipt)
    await robot.release("LEFT", "right_part", "left_target")
    robot.clear_event("right_ready", expected_version=left_receipt.version)
    await robot.move("LEFT", "left_depart")

    # --- RIGHT consumes LEFT's part ---
    right_receipt = await robot.wait_event("left_ready", 4)
    await robot.move("RIGHT", "right_pickup_wait")
    await robot.grasp("RIGHT", "left_part")
    await robot.move("RIGHT", "right_target", receipt=right_receipt)
    await robot.release("RIGHT", "left_part", "right_target")
    robot.clear_event("left_ready", expected_version=right_receipt.version)
    await robot.move("RIGHT", "right_depart")
