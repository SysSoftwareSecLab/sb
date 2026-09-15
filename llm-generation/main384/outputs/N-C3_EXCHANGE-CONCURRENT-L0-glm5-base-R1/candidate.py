import asyncio

from bridge_robot_api import Robot


async def _worker(robot: Robot, arm: str, own_part: str, own_source: str,
                  own_pad: str, own_pickup_wait: str, own_target: str,
                  own_depart: str, own_ready_event: str,
                  peer_part: str, peer_pad: str, peer_ready_event: str) -> None:
    # Phase 1: deposit own part on own pad, then clear the pad.
    await robot.move(arm, own_source)
    await robot.grasp(arm, own_part)
    await robot.move(arm, own_pad)
    await robot.release(arm, own_part, own_pad)
    await robot.move(arm, own_pickup_wait)

    # Publish own item-bound ready event after deposit/clear completed.
    own_receipt = robot.signal(own_ready_event, own_part)

    # Phase 2: wait for peer ready before picking up peer item.
    peer_receipt = await robot.wait_event(peer_ready_event, 30)

    # Phase 3: carry peer item to own target using the active peer receipt.
    await robot.move(arm, peer_pad, receipt=peer_receipt)
    await robot.grasp(arm, peer_part)
    await robot.move(arm, own_target)
    await robot.release(arm, peer_part, own_target)
    await robot.move(arm, own_depart)

    # Clear the peer ready event after the carrying move completed.
    robot.clear_event(peer_ready_event, expected_version=peer_receipt.version)

    # Clear own ready event (own item is no longer the active deposit).
    robot.clear_event(own_ready_event, expected_version=own_receipt.version)


async def run_task(robot: Robot) -> None:
    await asyncio.gather(
        _worker(
            robot,
            arm="LEFT",
            own_part="left_part",
            own_source="left_source",
            own_pad="left_pad",
            own_pickup_wait="left_pickup_wait",
            own_target="left_target",
            own_depart="left_depart",
            own_ready_event="left_ready",
            peer_part="right_part",
            peer_pad="right_pad",
            peer_ready_event="right_ready",
        ),
        _worker(
            robot,
            arm="RIGHT",
            own_part="right_part",
            own_source="right_source",
            own_pad="right_pad",
            own_pickup_wait="right_pickup_wait",
            own_target="right_target",
            own_depart="right_depart",
            own_ready_event="right_ready",
            peer_part="left_part",
            peer_pad="left_pad",
            peer_ready_event="left_ready",
        ),
    )
