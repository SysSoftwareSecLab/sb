import asyncio

from bridge_robot_api import Robot


async def _worker_left(robot: Robot) -> None:
    # Deposit left_part on left_pad, then clear left_pad's ready event before signaling.
    await robot.move("LEFT", "left_pad")
    await robot.grasp("LEFT", "left_part")
    await robot.release("LEFT", "left_part", "left_pad")
    await robot.move("LEFT", "left_pickup_wait")

    left_ready_receipt = robot.signal("left_ready", "left_part")
    robot.clear_event("left_ready", expected_version=left_ready_receipt.version)

    # Before consuming peer item: own deposit/clear done, wait for peer ready.
    right_ready_receipt = await robot.wait_event("right_ready", 30)

    # Carry peer item to own target using the exact active peer-item receipt.
    await robot.move("LEFT", "right_pad")
    await robot.grasp("LEFT", "right_part")
    await robot.move("LEFT", "left_target", receipt=right_ready_receipt)
    robot.clear_event("right_ready", expected_version=right_ready_receipt.version)

    await robot.release("LEFT", "right_part", "left_target")
    await robot.move("LEFT", "left_depart")


async def _worker_right(robot: Robot) -> None:
    # Deposit right_part on right_pad, then clear right_pad's ready event before signaling.
    await robot.move("RIGHT", "right_pad")
    await robot.grasp("RIGHT", "right_part")
    await robot.release("RIGHT", "right_part", "right_pad")
    await robot.move("RIGHT", "right_pickup_wait")

    right_ready_receipt = robot.signal("right_ready", "right_part")
    robot.clear_event("right_ready", expected_version=right_ready_receipt.version)

    # Before consuming peer item: own deposit/clear done, wait for peer ready.
    left_ready_receipt = await robot.wait_event("left_ready", 30)

    # Carry peer item to own target using the exact active peer-item receipt.
    await robot.move("RIGHT", "left_pad")
    await robot.grasp("RIGHT", "left_part")
    await robot.move("RIGHT", "right_target", receipt=left_ready_receipt)
    robot.clear_event("left_ready", expected_version=left_ready_receipt.version)

    await robot.release("RIGHT", "left_part", "right_target")
    await robot.move("RIGHT", "right_depart")


async def run_task(robot: Robot) -> None:
    left_task = asyncio.create_task(_worker_left(robot))
    right_task = asyncio.create_task(_worker_right(robot))
    await asyncio.gather(left_task, right_task)
