from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Phase A: each arm deposits its own part on its own pad, clears the
    # pad, then publishes its own item-bound ready event.
    # ------------------------------------------------------------------

    async def deposit_own(arm: str, part: str, source: str, pad: str,
                          ready_event: str) -> None:
        # Approach sequence: start_pose -> interaction_pose, then grasp
        # in the same coroutine at the same virtual instant.
        await robot.move(arm, source)
        await robot.grasp(arm, part)
        await robot.move(arm, pad)
        await robot.release(arm, part, pad)
        # Immediately begin separating departure from the pad.
        await robot.move(arm, "left_clear" if arm == "LEFT" else "right_clear")
        # Publish own item-bound ready event.
        robot.signal(ready_event, part)

    # ------------------------------------------------------------------
    # Phase B: each arm waits for the peer's ready event, then performs
    # the carried move to its own target using the exact active receipt,
    # then clears that event.
    # ------------------------------------------------------------------

    async def consume_peer(arm: str, peer_part: str, peer_ready: str,
                           pickup_wait: str, peer_pad: str,
                           target: str) -> None:
        # Wait for peer ready event.
        receipt = await robot.wait_event(peer_ready, 10.0)
        # Move to the pickup-wait pose for the peer item.
        await robot.move(arm, pickup_wait)
        # Approach sequence: pickup_wait -> peer_pad, then grasp.
        await robot.move(arm, peer_pad)
        await robot.grasp(arm, peer_part)
        # Carried move to own target, consuming the peer receipt.
        await robot.move(arm, target, receipt=receipt)
        # Clear the peer event after the carried move completes.
        robot.clear_event(peer_ready, expected_version=receipt.version)

    # ------------------------------------------------------------------
    # Orchestration: two workers, one per arm.
    # ------------------------------------------------------------------

    async def left_worker() -> None:
        await deposit_own("LEFT", "left_part", "left_source", "left_pad",
                          "left_ready")
        await consume_peer("LEFT", "right_part", "right_ready",
                           "left_pickup_wait", "right_pad", "left_target")

    async def right_worker() -> None:
        await deposit_own("RIGHT", "right_part", "right_source", "right_pad",
                          "right_ready")
        await consume_peer("RIGHT", "left_part", "left_ready",
                           "right_pickup_wait", "left_pad", "right_target")

    await asyncio.gather(left_worker(), right_worker())
