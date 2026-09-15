from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Phase 1: each arm deposits its own part on its own pad, then clears
    # the pad, then publishes its own item-bound ready event.
    # ------------------------------------------------------------------

    async def deposit_own(arm: str, part: str, source: str, pad: str,
                          clear_pose: str, ready_event: str) -> None:
        # Approach own source from home, then immediately grasp.
        await robot.move(arm, source)
        await robot.grasp(arm, part)
        # Carry to own pad and release there.
        await robot.move(arm, pad)
        await robot.release(arm, part, pad)
        # Immediately clear the pad (same coroutine, same virtual instant).
        await robot.move(arm, clear_pose)
        # Publish own item-bound ready event.
        robot.signal(ready_event, part)

    # ------------------------------------------------------------------
    # Phase 2: each arm waits for the peer's ready event, then picks up
    # the peer item from the peer's pad, carries it to its own target,
    # releases it, and clears the event after the carried move.
    # ------------------------------------------------------------------

    async def consume_peer(arm: str, peer_part: str, peer_pad: str,
                           pickup_wait: str, target: str,
                           peer_ready_event: str) -> None:
        # Wait for peer ready (must complete before picking up peer item).
        receipt = await robot.wait_event(peer_ready_event, 30)
        # Move to the pickup wait pose, then approach peer pad and grasp.
        await robot.move(arm, pickup_wait)
        await robot.move(arm, peer_pad)
        await robot.grasp(arm, peer_part)
        # Carried move to own target, using the exact active peer receipt.
        await robot.move(arm, target, receipt=receipt)
        # Release peer item on own target.
        await robot.release(arm, peer_part, target)
        # Clear the peer ready event after the carried move completed.
        robot.clear_event(peer_ready_event, expected_version=receipt.version)

    # ------------------------------------------------------------------
    # Structure A: deposit LEFT then RIGHT, then consume LEFT then RIGHT.
    # ------------------------------------------------------------------

    await deposit_own("LEFT", "left_part", "left_source", "left_pad",
                      "left_clear", "left_ready")
    await deposit_own("RIGHT", "right_part", "right_source", "right_pad",
                      "right_clear", "right_ready")

    await consume_peer("LEFT", "right_part", "right_pad",
                       "left_pickup_wait", "left_target", "right_ready")
    await consume_peer("RIGHT", "left_part", "left_pad",
                       "right_pickup_wait", "right_target", "left_ready")

    # ------------------------------------------------------------------
    # Final: empty arms at own departure poses.
    # ------------------------------------------------------------------

    await robot.move("LEFT", "left_depart")
    await robot.move("RIGHT", "right_depart")
