import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    """IC03_C3_EXCHANGE-OOD-DEVELOPMENT_SHAPE, variant A, SERIAL layout L0.

    Structure: FOR -> IF -> PAR_JOIN. The IF contains the join and the
    consumer itself has no mission guard. Inside one finite loop iteration
    we concurrently join an rq2_gate producer and consumer; the consumer
    waits the exact active receipt, executes the complete inherited mission,
    then clears that version.
    """

    async def deposit_and_clear(arm: str, part: str, source: str,
                                pad: str, clear_pose: str,
                                wait_pose: str, ready_event: str) -> None:
        """Deposit own part on own pad, clear the pad, publish ready event."""
        await robot.move(arm, source)
        await robot.grasp(arm, part)
        await robot.move(arm, pad)
        await robot.release(arm, part, pad)
        await robot.move(arm, clear_pose)
        robot.signal(ready_event, part)
        await robot.move(arm, wait_pose)

    async def consume_peer(arm: str, peer_part: str, peer_pad: str,
                           wait_pose: str, target: str,
                           depart: str, ready_event: str,
                           receipt) -> None:
        """Wait for peer ready, carry peer item to own target, clear event."""
        await robot.wait_event(ready_event, 30)
        await robot.move(arm, peer_pad, receipt=receipt)
        await robot.grasp(arm, peer_part)
        await robot.move(arm, target, receipt=receipt)
        robot.clear_event(ready_event, expected_version=receipt.version)
        await robot.move(arm, depart)

    async def rq2_gate_producer() -> None:
        """Producer: signal rq2_gate (version 1)."""
        robot.signal("rq2_gate")

    async def rq2_gate_consumer(receipt) -> None:
        """Consumer: wait exact active receipt, run inherited mission, clear."""
        await robot.wait_event("rq2_gate", 30)
        await robot.move("LEFT", "left_home", receipt=receipt)
        await robot.move("RIGHT", "right_home", receipt=receipt)
        robot.clear_event("rq2_gate", expected_version=receipt.version)

    # FOR: one finite loop iteration.
    for _ in range(1):
        # Deposit LEFT then RIGHT (serial order A).
        await deposit_and_clear(
            "LEFT", "left_part", "left_source", "left_pad",
            "left_clear", "left_pickup_wait", "left_ready"
        )
        await deposit_and_clear(
            "RIGHT", "right_part", "right_source", "right_pad",
            "right_clear", "right_pickup_wait", "right_ready"
        )

        # Pre-signal rq2_gate so an active receipt exists for the consumer.
        gate_receipt = robot.signal("rq2_gate")

        # IF: contains the join; consumer has no mission guard.
        if True:
            # PAR_JOIN: concurrently join producer and consumer.
            await asyncio.gather(
                rq2_gate_producer(),
                rq2_gate_consumer(gate_receipt),
            )

        # Consume LEFT then RIGHT (serial order A).
        left_receipt = robot.signal("left_ready", "left_part")
        await consume_peer(
            "RIGHT", "left_part", "left_pad", "right_pickup_wait",
            "left_target", "right_depart", "left_ready", left_receipt
        )
        right_receipt = robot.signal("right_ready", "right_part")
        await consume_peer(
            "LEFT", "right_part", "right_pad", "left_pickup_wait",
            "right_target", "left_depart", "right_ready", right_receipt
        )
