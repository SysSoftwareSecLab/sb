import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    left_ready_receipt: EventReceipt | None = None
    right_ready_receipt: EventReceipt | None = None

    async def left_worker() -> None:
        nonlocal left_ready_receipt
        # Approach left_part from left_home, then immediately grasp.
        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        # Verify left_part.
        await robot.inspect("LEFT", "left_verification")
        # Signal left_ready.
        left_ready_receipt = robot.signal("left_ready", "left_part")

    async def right_worker() -> None:
        nonlocal right_ready_receipt
        # Approach right_part from right_home, then immediately grasp.
        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", "right_source")
        await robot.grasp("RIGHT", "right_part")
        # Verify right_part.
        await robot.inspect("RIGHT", "right_verification")
        # Signal right_ready.
        right_ready_receipt = robot.signal("right_ready", "right_part")

    # Run both verifier branches concurrently and join.
    await asyncio.gather(left_worker(), right_worker())

    # Wait for both join events to be active.
    left_ev = await robot.wait_event("left_ready", 5)
    right_ev = await robot.wait_event("right_ready", 5)

    # Consume both receipts via moves (payload consumer).
    await robot.move("LEFT", "left_target", receipt=left_ev)
    await robot.move("RIGHT", "right_target", receipt=right_ev)

    # Clear events after the corresponding moves have completed.
    robot.clear_event("left_ready", expected_version=left_ev.version)
    robot.clear_event("right_ready", expected_version=right_ev.version)

    # Release parts at targets.
    await robot.release("LEFT", "left_part", "left_target")
    await robot.release("RIGHT", "right_part", "right_target")

    # Depart.
    await robot.move("LEFT", "left_depart")
    await robot.move("RIGHT", "right_depart")
