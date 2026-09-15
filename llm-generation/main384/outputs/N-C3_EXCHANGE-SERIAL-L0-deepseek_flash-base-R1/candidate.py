from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # Variant A: serialized execution.
    # Step 1: LEFT deposits left_part on left_pad, clears, signals left_ready.
    # Step 2: RIGHT deposits right_part on right_pad, clears, signals right_ready.
    # Step 3: LEFT waits for right_ready, picks up right_part, carries to left_target, clears right_ready.
    # Step 4: RIGHT waits for left_ready, picks up left_part, carries to right_target, clears left_ready.

    # --- LEFT deposit phase ---
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_pad")
    await robot.release("LEFT", "left_part", "left_pad")
    await robot.move("LEFT", "left_clear")
    left_ready_receipt = robot.signal("left_ready", "left_part")

    # --- RIGHT deposit phase ---
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_pad")
    await robot.release("RIGHT", "right_part", "right_pad")
    await robot.move("RIGHT", "right_clear")
    right_ready_receipt = robot.signal("right_ready", "right_part")

    # --- LEFT consume phase ---
    # Wait for peer (RIGHT) ready before picking up right_part.
    left_wait_receipt = await robot.wait_event("right_ready", 5.0)
    await robot.move("LEFT", "left_pickup_wait")
    await robot.grasp("LEFT", "right_part")
    await robot.move("LEFT", "left_target", receipt=left_wait_receipt)
    await robot.release("LEFT", "right_part", "left_target")
    await robot.move("LEFT", "left_depart")
    robot.clear_event("right_ready", expected_version=left_wait_receipt.version)

    # --- RIGHT consume phase ---
    right_wait_receipt = await robot.wait_event("left_ready", 5.0)
    await robot.move("RIGHT", "right_pickup_wait")
    await robot.grasp("RIGHT", "left_part")
    await robot.move("RIGHT", "right_target", receipt=right_wait_receipt)
    await robot.release("RIGHT", "left_part", "right_target")
    await robot.move("RIGHT", "right_depart")
    robot.clear_event("left_ready", expected_version=right_wait_receipt.version)
