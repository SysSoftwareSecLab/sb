from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    left_ready = robot.signal("left_ready")
    right_ready = robot.signal("right_ready")

    async def left_worker():
        # Deposit own part on own pad
        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "left_pad")
        await robot.release("LEFT", "left_part", "left_pad")
        await robot.move("LEFT", "left_clear")
        robot.clear_event("left_ready", expected_version=left_ready.version)

        # Wait for peer ready
        peer = await robot.wait_event("right_ready", timeout_s=10)

        # Consume peer item
        await robot.move("LEFT", "left_pickup_wait")
        await robot.grasp("LEFT", "right_part")
        await robot.move("LEFT", "left_target", receipt=peer)
        await robot.release("LEFT", "right_part", "left_target")
        robot.clear_event("right_ready", expected_version=peer.version)
        await robot.move("LEFT", "left_depart")

    async def right_worker():
        # Deposit own part on own pad
        await robot.move("RIGHT", "right_source")
        await robot.grasp("RIGHT", "right_part")
        await robot.move("RIGHT", "right_pad")
        await robot.release("RIGHT", "right_part", "right_pad")
        await robot.move("RIGHT", "right_clear")
        robot.clear_event("right_ready", expected_version=right_ready.version)

        # Wait for peer ready
        peer = await robot.wait_event("left_ready", timeout_s=10)

        # Consume peer item
        await robot.move("RIGHT", "right_pickup_wait")
        await robot.grasp("RIGHT", "left_part")
        await robot.move("RIGHT", "right_target", receipt=peer)
        await robot.release("RIGHT", "left_part", "right_target")
        robot.clear_event("left_ready", expected_version=peer.version)
        await robot.move("RIGHT", "right_depart")

    await asyncio.gather(left_worker(), right_worker())
