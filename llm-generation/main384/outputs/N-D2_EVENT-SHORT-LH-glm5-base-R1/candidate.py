import asyncio
from bridge_robot_api import Robot


async def _left_worker(robot: Robot) -> None:
    # LEFT deposits left_part on left_pad, clears, signals left_ready.
    await robot.move("LEFT", "left_pad")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_pad")
    await robot.release("LEFT", "left_part", "left_pad")
    await robot.move("LEFT", "left_clear")
    left_ready_receipt = robot.signal("left_ready", "left_part")
    # Before picking up peer item: own deposit/clear done and wait for peer ready.
    right_ready_receipt = await robot.wait_event("right_ready", 30)
    # Move to pickup wait, then approach right_part from left_pickup_wait.
    await robot.move("LEFT", "left_pickup_wait")
    # Approach sequence: start left_pickup_wait -> interaction right_pad -> grasp right_part.
    await robot.move("LEFT", "right_pad", receipt=right_ready_receipt)
    await robot.grasp("LEFT", "right_part")
    # Carry peer item to LEFT's own target (right_target).
    await robot.move("LEFT", "right_target")
    # Clear the consumed peer-item ready event after the carried move completes.
    robot.clear_event("right_ready", expected_version=right_ready_receipt.version)
    await robot.release("LEFT", "right_part", "right_target")
    await robot.move("LEFT", "left_depart")


async def _right_worker(robot: Robot) -> None:
    # RIGHT deposits right_part on right_pad, clears, signals right_ready.
    await robot.move("RIGHT", "right_pad")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_pad")
    await robot.release("RIGHT", "right_part", "right_pad")
    await robot.move("RIGHT", "right_clear")
    right_ready_receipt = robot.signal("right_ready", "right_part")
    # Before picking up peer item: own deposit/clear done and wait for peer ready.
    left_ready_receipt = await robot.wait_event("left_ready", 30)
    # Move to pickup wait, then approach left_part from right_pickup_wait.
    await robot.move("RIGHT", "right_pickup_wait")
    # Approach sequence: start right_pickup_wait -> interaction left_pad -> grasp left_part.
    await robot.move("RIGHT", "left_pad", receipt=left_ready_receipt)
    await robot.grasp("RIGHT", "left_part")
    # Carry peer item to RIGHT's own target (left_target).
    await robot.move("RIGHT", "left_target")
    # Clear the consumed peer-item ready event after the carried move completes.
    robot.clear_event("left_ready", expected_version=left_ready_receipt.version)
    await robot.release("RIGHT", "left_part", "left_target")
    await robot.move("RIGHT", "right_depart")


async def run_task(robot: Robot) -> None:
    await asyncio.gather(_left_worker(robot), _right_worker(robot))
