import asyncio

from bridge_robot_api import Robot


async def _left_worker(robot: Robot) -> None:
    # Deposit LEFT's own part (left_part) on left_pad, then clear left_ready.
    await robot.move("LEFT", "left_source")
    left_grasp_obs = await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_pad")
    await robot.release("LEFT", "left_part", "left_pad")
    await robot.move("LEFT", "left_pickup_wait")
    left_ready_receipt = robot.signal("left_ready", "left_part")
    # Before consuming peer item: own deposit/clear done, and wait for peer ready.
    right_ready_receipt = await robot.wait_event("right_ready", 30)
    # Approach peer item from left_pickup_wait to right_pad, immediately grasp.
    await robot.move("LEFT", "right_pad")
    await robot.grasp("LEFT", "right_part", observation=right_ready_receipt)
    # Carried move to own target must carry the exact active peer-item receipt.
    await robot.move("LEFT", "left_target", receipt=right_ready_receipt)
    # Clear that event after the carried move completes.
    robot.clear_event("right_ready", expected_version=right_ready_receipt.version)
    await robot.release("LEFT", "right_part", "left_target")
    await robot.move("LEFT", "left_depart")
    robot.clear_event("left_ready", expected_version=left_ready_receipt.version)


async def _right_worker(robot: Robot) -> None:
    # Deposit RIGHT's own part (right_part) on right_pad, then clear right_ready.
    await robot.move("RIGHT", "right_source")
    right_grasp_obs = await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_pad")
    await robot.release("RIGHT", "right_part", "right_pad")
    await robot.move("RIGHT", "right_pickup_wait")
    right_ready_receipt = robot.signal("right_ready", "right_part")
    # Before consuming peer item: own deposit/clear done, and wait for peer ready.
    left_ready_receipt = await robot.wait_event("left_ready", 30)
    # Approach peer item from right_pickup_wait to left_pad, immediately grasp.
    await robot.move("RIGHT", "left_pad")
    await robot.grasp("RIGHT", "left_part", observation=left_ready_receipt)
    # Carried move to own target must carry the exact active peer-item receipt.
    await robot.move("RIGHT", "right_target", receipt=left_ready_receipt)
    # Clear that event after the carried move completes.
    robot.clear_event("left_ready", expected_version=left_ready_receipt.version)
    await robot.release("RIGHT", "left_part", "right_target")
    await robot.move("RIGHT", "right_depart")
    robot.clear_event("right_ready", expected_version=right_ready_receipt.version)


async def run_task(robot: Robot) -> None:
    await asyncio.gather(_left_worker(robot), _right_worker(robot))
