import asyncio
from bridge_robot_api import Robot


async def _deposit_and_clear(robot: Robot, arm: str, part: str, home: str,
                            source: str, pad: str, clear: str,
                            depart: str, ready_event: str) -> None:
    """Deposit own part on own pad, clear pad, then publish own ready event."""
    # Approach own part from home to source, immediately grasp.
    await robot.move(arm, source)
    await robot.grasp(arm, part)

    # Carry to own pad.
    await robot.move(arm, pad)

    # Release onto pad (support_zone must equal current named pose).
    await robot.release(arm, part, pad)

    # Immediate separating departure from the pad.
    await robot.move(arm, clear)

    # Clear own pad event (pad now empty) before publishing ready.
    # The ready event is item-bound; signal it after deposit+clear.
    robot.signal(ready_event, part)


async def _consume_peer(robot: Robot, arm: str, peer_part: str,
                        pickup_wait: str, peer_pad: str,
                        target: str, depart: str,
                        peer_ready_event: str) -> None:
    """Wait for peer ready, pick up peer item, carry to own target, clear event."""
    # Wait for peer's ready event (returns active EventReceipt for peer item).
    receipt = await robot.wait_event(peer_ready_event, 30)

    # Move to pickup wait pose, then approach peer item on peer pad.
    await robot.move(arm, pickup_wait)
    await robot.move(arm, peer_pad)

    # Grasp peer item (approach sequence: start_pose=pickup_wait -> peer_pad -> grasp).
    await robot.grasp(arm, peer_part)

    # Carried move to own target using the exact active peer-item receipt.
    await robot.move(arm, target, receipt=receipt)

    # Clear that event after the carried move completes.
    robot.clear_event(peer_ready_event, expected_version=receipt.version)

    # Release peer item onto own target.
    await robot.release(arm, peer_part, target)

    # Immediate separating departure to own depart pose.
    await robot.move(arm, depart)


async def run_task(robot: Robot) -> None:
    """C3_EXCHANGE-SERIAL-L0, variant A.

    Required order (variant A): deposit LEFT then RIGHT, then consume LEFT
    then RIGHT. Both arms exchange distinct payloads through separate pads.
    """
    # Phase 1: deposit LEFT, then deposit RIGHT (serial).
    await _deposit_and_clear(
        robot, "LEFT", "left_part",
        "left_home", "left_source", "left_pad", "left_clear",
        "left_depart", "left_ready",
    )
    await _deposit_and_clear(
        robot, "RIGHT", "right_part",
        "right_home", "right_source", "right_pad", "right_clear",
        "right_depart", "right_ready",
    )

    # Phase 2: consume LEFT (peer=right), then consume RIGHT (peer=left) (serial).
    await _consume_peer(
        robot, "LEFT", "right_part",
        "left_pickup_wait", "right_pad",
        "left_target", "left_depart",
        "right_ready",
    )
    await _consume_peer(
        robot, "RIGHT", "left_part",
        "right_pickup_wait", "left_pad",
        "right_target", "right_depart",
        "left_ready",
    )
