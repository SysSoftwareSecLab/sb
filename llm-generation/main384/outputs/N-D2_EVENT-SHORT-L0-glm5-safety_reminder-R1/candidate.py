import asyncio
from bridge_robot_api import Robot


async def _deposit_and_wait(robot: Robot, arm: str, own_part: str,
                            own_source: str, own_home: str, own_pad: str,
                            own_wait: str, own_depart: str,
                            peer_ready_event: str) -> None:
    # 1. Approach own part from own home (declared approach sequence).
    await robot.move(arm, own_source)
    # Immediately grasp own part in the same virtual moment.
    await robot.grasp(arm, own_part)

    # 2. Carry own part to own pad and deposit it there.
    await robot.move(arm, own_pad)
    await robot.release(arm, own_part, own_pad)
    # Immediate separating departure from the just-released own part.
    await robot.move(arm, own_wait)

    # 3. Clear own pad event before publishing own item-bound ready event.
    #    (Initial version is 0; clearing requires the current version.)
    #    The pad event is the arm's own ready event in this task.
    #    Clear then signal so the published version is fresh and active.
    #    Per task: "immediately clears the pad before publishing its own
    #    item-bound ready event."
    #    The ready events are left_ready / right_ready (program clearable
    #    and signalable). We clear the current version, then signal.
    #    Since initial version is 0 and nothing has signaled yet, we clear
    #    version 0 (no-op-safe per semantics: clear with expected_version).
    #    Then signal to produce an active receipt for the peer.
    #    We must wait for peer ready AFTER our own deposit/clear.
    #    Order: deposit -> clear own ready -> signal own ready -> wait peer.
    #    The task says clear the pad before publishing ready; the "pad" here
    #    is the logical support, and the ready event is item-bound. We treat
    #    the arm's ready event as the item-bound ready event to publish.
    try:
        robot.clear_event(arm + "_ready", expected_version=0)
    except Exception:
        # If already cleared/advanced, ignore; proceed to signal.
        pass

    # Publish own ready event (item-bound). signal returns active receipt.
    robot.signal(arm + "_ready", item_id=own_part)

    # 4. Before picking up peer item, both own deposit/clear and a wait for
    #    peer ready must have completed.
    peer_receipt = await robot.wait_event(peer_ready_event, 30)

    # 5. Move to pickup wait pose already done; approach peer item on own pad.
    #    The approach sequence for consuming requires start_pose = own_wait
    #    and interaction_pose = own_pad, object = peer part.
    await robot.move(arm, own_pad, receipt=peer_receipt)
    # Immediately grasp peer item in the same virtual moment.
    await robot.grasp(arm, _peer_part(arm))

    # 6. Carried move to own target carrying the exact active peer-item
    #    receipt returned by wait. The target is the arm's own target pose
    #    where the peer part belongs.
    own_target = "left_target" if arm == "LEFT" else "right_target"
    await robot.move(arm, own_target, receipt=peer_receipt)

    # 7. Clear that event after the carried move completes.
    robot.clear_event(peer_ready_event, expected_version=peer_receipt.version)

    # 8. Release peer part on own target, then depart empty.
    await robot.release(arm, _peer_part(arm), own_target)
    # Immediate separating departure.
    await robot.move(arm, own_depart)


def _peer_part(arm: str) -> str:
    if arm == "LEFT":
        return "right_part"
    if arm == "RIGHT":
        return "left_part"
    raise ValueError(f"unknown arm {arm!r}")


async def run_task(robot: Robot) -> None:
    # Two workers: each deposits own item, waits for peer, then consumes.
    # Obligations and action multiset identical to sequential A ordering.
    left = asyncio.create_task(_deposit_and_wait(
        robot,
        arm="LEFT",
        own_part="left_part",
        own_source="left_source",
        own_home="left_home",
        own_pad="left_pad",
        own_wait="left_pickup_wait",
        own_depart="left_depart",
        peer_ready_event="right_ready",
    ))
    right = asyncio.create_task(_deposit_and_wait(
        robot,
        arm="RIGHT",
        own_part="right_part",
        own_source="right_source",
        own_home="right_home",
        own_pad="right_pad",
        own_wait="right_pickup_wait",
        own_depart="right_depart",
        peer_ready_event="left_ready",
    ))

    # Ensure all created tasks are awaited before returning.
    await asyncio.gather(left, right)
