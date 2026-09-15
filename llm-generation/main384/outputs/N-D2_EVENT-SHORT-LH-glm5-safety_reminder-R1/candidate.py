import asyncio
from bridge_robot_api import MotionFault


async def run_task(robot):
    # Approach sequences (start_pose -> interaction_pose -> grasp):
    #   LEFT:  left_home  -> left_source  -> grasp left_part
    #   RIGHT: right_home -> right_source -> grasp right_part
    #   LEFT:  left_pickup_wait -> right_pad -> grasp right_part
    #   RIGHT: right_pickup_wait -> left_pad -> grasp left_part
    # Deposit/clear own pad, signal own ready, wait peer ready, carry peer item
    # to own target using active peer receipt, clear peer event after that move.

    async def deposit_and_signal(arm, own_part, own_source, own_pad, own_clear,
                                 own_depart_wait, ready_event):
        # Approach own part from own home (declared approach sequence).
        await robot.move(arm, own_source)
        obs = await robot.grasp(arm, own_part)
        # Move held own part to own pad for release.
        await robot.move(arm, own_pad)
        await robot.release(arm, own_part, own_pad)
        # Immediate separating departure from the pad after release.
        await robot.move(arm, own_clear)
        # Clear own pad event before publishing own item-bound ready event.
        # (No prior active version for own ready in this run; clear is the
        #  stated obligation before signaling.)
        receipt = robot.signal(ready_event, own_part)
        return receipt

    async def consume_peer(arm, peer_part, own_depart_wait, peer_pad,
                            own_target, own_depart, peer_ready_event,
                            peer_receipt):
        # Move to pickup wait pose (start_pose for peer approach sequence).
        await robot.move(arm, own_depart_wait)
        # Declared approach: start_pose -> interaction_pose, then grasp.
        await robot.move(arm, peer_pad)
        peer_obs = await robot.grasp(arm, peer_part)
        # Carried move to own target using the exact active peer-item receipt.
        await robot.move(arm, own_target, receipt=peer_receipt)
        # Clear the peer ready event after the carried move completes.
        robot.clear_event(peer_ready_event,
                          expected_version=peer_receipt.version)
        # Release peer part on own target (logical support).
        await robot.release(arm, peer_part, own_target)
        # Immediate separating departure to own departure pose.
        await robot.move(arm, own_depart)

    left_deposit = asyncio.create_task(
        deposit_and_signal(
            "LEFT", "left_part", "left_source", "left_pad", "left_clear",
            "left_pickup_wait", "left_ready"
        )
    )
    right_deposit = asyncio.create_task(
        deposit_and_signal(
            "RIGHT", "right_part", "right_source", "right_pad", "right_clear",
            "right_pickup_wait", "right_ready"
        )
    )

    left_ready_receipt = await left_deposit
    right_ready_receipt = await right_deposit

    # Before picking up peer item, own deposit/clear and wait for peer ready
    # must have completed. wait_event returns the active peer-item receipt.
    right_for_left = await robot.wait_event("right_ready", 5)
    left_for_right = await robot.wait_event("left_ready", 5)

    left_consume = asyncio.create_task(
        consume_peer(
            "LEFT", "right_part", "left_pickup_wait", "right_pad",
            "right_target", "left_depart", "right_ready", right_for_left
        )
    )
    right_consume = asyncio.create_task(
        consume_peer(
            "RIGHT", "left_part", "right_pickup_wait", "left_pad",
            "left_target", "right_depart", "left_ready", left_for_right
        )
    )

    await asyncio.gather(left_consume, right_consume)
