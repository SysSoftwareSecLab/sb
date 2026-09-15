import asyncio
from bridge_robot_api import MotionFault


async def _move(robot, arm, pose, timeout=None):
    return await robot.move(arm, pose, timeout_s=timeout)


async def _deposit_and_clear(robot, arm, own_part, own_source, own_pad,
                             own_pickup_wait, own_clear, own_depart,
                             ready_event, peer_ready_event):
    """Deposit own part on own pad, clear pad, signal own ready event."""
    # Approach own source from home and grasp own part.
    await _move(robot, arm, own_source)
    await robot.grasp(arm, own_part)

    # Move to own pad and release onto it.
    await _move(robot, arm, own_pad)
    await robot.release(arm, own_part, own_pad)

    # Immediately depart from the pad to the pickup-wait pose.
    await _move(robot, arm, own_pickup_wait)

    # Signal own ready event (item-bound).
    receipt = robot.signal(ready_event, own_part)

    # Wait for peer ready event before consuming.
    peer_receipt = await robot.wait_event(peer_ready_event, 30)

    # Move to peer's pad (where peer deposited its part) and grasp it.
    # The carried move must use the exact active peer-item receipt.
    if arm == "LEFT":
        peer_pad = "right_pad"
    else:
        peer_pad = "left_pad"
    await _move(robot, arm, peer_pad, receipt=peer_receipt)
    await robot.grasp(arm, "right_part" if arm == "LEFT" else "left_part")

    # Move to own target and release the peer part there.
    own_target = "left_target" if arm == "LEFT" else "right_target"
    await _move(robot, arm, own_target)
    peer_part = "right_part" if arm == "LEFT" else "left_part"
    await robot.release(arm, peer_part, own_target)

    # Immediately depart to own clear pose, then own depart.
    await _move(robot, arm, own_clear)
    await _move(robot, arm, own_depart)

    # Clear the peer ready event after the carried move is complete.
    robot.clear_event(peer_ready_event, expected_version=peer_receipt.version)

    # Clear own ready event.
    robot.clear_event(ready_event, expected_version=receipt.version)


async def run_task(robot):
    left_task = _deposit_and_clear(
        robot, "LEFT", "left_part", "left_source", "left_pad",
        "left_pickup_wait", "left_clear", "left_depart",
        "left_ready", "right_ready"
    )
    right_task = _deposit_and_clear(
        robot, "RIGHT", "right_part", "right_source", "right_pad",
        "right_pickup_wait", "right_clear", "right_depart",
        "right_ready", "left_ready"
    )
    await asyncio.gather(left_task, right_task)
