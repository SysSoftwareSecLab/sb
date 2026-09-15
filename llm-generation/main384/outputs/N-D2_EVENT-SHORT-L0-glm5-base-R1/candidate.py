import asyncio

from bridge_robot_api import Robot


async def _deposit_and_wait(robot: Robot, arm: str, own_part: str,
                            own_source: str, own_home: str, own_pad: str,
                            own_pickup_wait: str, own_clear: str,
                            own_depart: str, peer_ready_event: str) -> None:
    """Deposit own part on own pad, clear pad, publish own ready, wait peer."""
    # Move from home to source and immediately grasp own part.
    await robot.move(arm, own_source)
    await robot.grasp(arm, own_part)

    # Move to own pad and release own part there.
    await robot.move(arm, own_pad)
    await robot.release(arm, own_part, own_pad)

    # Immediately separate from the just-released object.
    await robot.move(arm, own_clear)

    # Pad is clear; publish own item-bound ready event.
    robot.signal(peer_ready_event, own_part)


async def _consume_and_depart(robot: Robot, arm: str, peer_part: str,
                              peer_pad: str, pickup_wait: str,
                              own_target: str, own_depart: str,
                              peer_ready_event: str) -> None:
    """Wait for peer ready, pick up peer item, carry to target, clear event."""
    # Wait for peer's item-bound ready event.
    receipt = await robot.wait_event(peer_ready_event, 30)

    # Move to pickup-wait pose, then approach peer item and grasp immediately.
    await robot.move(arm, pickup_wait)
    await robot.move(arm, peer_pad, receipt=receipt)
    await robot.grasp(arm, peer_part, observation=receipt)

    # Carry peer item to own target and release it there.
    await robot.move(arm, own_target, receipt=receipt)
    await robot.release(arm, peer_part, own_target)

    # Clear the consumed peer ready event after the carried move completed.
    clear_event = robot.clear_event
    clear_event(peer_ready_event, expected_version=receipt.version)

    # Depart to own departure pose with empty arm.
    await robot.move(arm, own_depart)


async def run_task(robot: Robot) -> None:
    left_deposit = asyncio.create_task(
        _deposit_and_wait(
            robot, "LEFT", "left_part", "left_source", "left_home",
            "left_pad", "left_pickup_wait", "left_clear", "left_depart",
            "left_ready",
        )
    )
    right_deposit = asyncio.create_task(
        _deposit_and_wait(
            robot, "RIGHT", "right_part", "right_source", "right_home",
            "right_pad", "right_pickup_wait", "right_clear", "right_depart",
            "right_ready",
        )
    )

    await left_deposit
    await right_deposit

    left_consume = asyncio.create_task(
        _consume_and_depart(
            robot, "LEFT", "right_part", "right_pad", "left_pickup_wait",
            "left_target", "left_depart", "right_ready",
        )
    )
    right_consume = asyncio.create_task(
        _consume_and_depart(
            robot, "RIGHT", "left_part", "left_pad", "right_pickup_wait",
            "right_target", "right_depart", "left_ready",
        )
    )

    await left_consume
    await right_consume
