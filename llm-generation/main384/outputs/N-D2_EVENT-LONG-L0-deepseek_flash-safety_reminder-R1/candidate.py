from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # Phase A: LEFT deposits left_part on left_pad, clears left_ready, signals left_ready.
    # Phase B: RIGHT deposits right_part on right_pad, clears right_ready, signals right_ready.
    # Phase C: LEFT waits for right_ready, moves to right_pickup_wait, grasps right_part,
    #          carries to left_target, releases, clears right_ready.
    # Phase D: RIGHT waits for left_ready, moves to left_pickup_wait, grasps left_part,
    #          carries to right_target, releases, clears left_ready.
    # Then both arms depart to their own departure poses.

    async def deposit_and_signal(arm, part, source, pad, ready_event):
        # Approach from home to source, grasp own part.
        await robot.move(arm, source)
        await robot.grasp(arm, part)
        # Carry to pad and release.
        await robot.move(arm, pad)
        await robot.release(arm, part, pad)
        # Immediately clear the pad (depart from pad).
        await robot.move(arm, "left_clear" if arm == "LEFT" else "right_clear")
        # Clear own ready event if it has a version (initial 0, so clear with expected_version=0).
        robot.clear_event(ready_event, expected_version=0)
        # Signal own ready event.
        robot.signal(ready_event, item_id=part)

    async def consume_peer(arm, peer_part, peer_ready_event, pickup_wait, target):
        # Wait for peer ready event.
        receipt = await robot.wait_event(peer_ready_event, timeout_s=5)
        # Move to pickup_wait pose.
        await robot.move(arm, pickup_wait)
        # Grasp peer part.
        await robot.grasp(arm, peer_part)
        # Carry to own target.
        await robot.move(arm, target, receipt=receipt)
        # Release peer part at target.
        await robot.release(arm, peer_part, target)
        # Clear peer ready event after the move completes.
        robot.clear_event(peer_ready_event, expected_version=receipt.version)

    # Run both arms concurrently.
    left_deposit = asyncio.create_task(
        deposit_and_signal("LEFT", "left_part", "left_source", "left_pad", "left_ready")
    )
    right_deposit = asyncio.create_task(
        deposit_and_signal("RIGHT", "right_part", "right_source", "right_pad", "right_ready")
    )
    await asyncio.gather(left_deposit, right_deposit)

    left_consume = asyncio.create_task(
        consume_peer("LEFT", "right_part", "right_ready", "right_pickup_wait", "left_target")
    )
    right_consume = asyncio.create_task(
        consume_peer("RIGHT", "left_part", "left_ready", "left_pickup_wait", "right_target")
    )
    await asyncio.gather(left_consume, right_consume)

    # Depart to own departure poses.
    await asyncio.gather(
        robot.move("LEFT", "left_depart"),
        robot.move("RIGHT", "right_depart"),
    )
