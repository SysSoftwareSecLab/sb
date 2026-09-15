import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    """C3_EXCHANGE-SERIAL-LH, variant A.

    Stated structure: deposit LEFT then RIGHT, then consume LEFT then RIGHT.
    Each deposit: approach -> grasp -> move to own pad -> release -> immediate
    separating departure -> clear own ready event. Each consume: move to pickup
    wait -> wait for peer ready -> approach peer item on peer pad -> grasp ->
    carry move to own target using the active peer-item receipt -> clear that
    event -> depart.
    """

    async def deposit(arm: str, own_part: str, own_source: str, own_pad: str,
                       own_wait: str, own_clear: str, own_depart: str,
                       ready_event: str) -> None:
        # Approach own part from own home (start_pose) to own source.
        await robot.move(arm, own_source)
        # Same virtual moment, same candidate coroutine: grasp immediately.
        await robot.grasp(arm, own_part)
        # Carry own part to own pad.
        await robot.move(arm, own_pad)
        # Release on own pad (current pose == support_zone).
        await robot.release(arm, own_part, own_pad)
        # Immediate separating departure from the pad.
        await robot.move(arm, own_clear)
        # Move to pickup wait pose for later peer consumption.
        await robot.move(arm, own_wait)
        # Publish own item-bound ready event after deposit/clear completed.
        receipt = robot.signal(ready_event, own_part)
        # Clear own ready event (pad already cleared by departure).
        robot.clear_event(ready_event, expected_version=receipt.version)

    async def consume(arm: str, peer_part: str, peer_pad: str, own_wait: str,
                      own_target: str, own_depart: str,
                      peer_ready_event: str) -> None:
        # Ensure at pickup wait pose (start_pose for peer-item approach).
        await robot.move(arm, own_wait)
        # Before pickup: wait for peer ready (peer deposit/clear completed).
        peer_receipt = await robot.wait_event(peer_ready_event, 30)
        # Approach peer item from wait pose to peer pad; grasp immediately.
        await robot.move(arm, peer_pad)
        await robot.grasp(arm, peer_part)
        # Carried move to own target using exact active peer-item receipt.
        await robot.move(arm, own_target, receipt=peer_receipt)
        # Clear that event after the carrying move truly completed.
        robot.clear_event(peer_ready_event, expected_version=peer_receipt.version)
        # Depart to own departure pose; empty arm at own departure.
        await robot.move(arm, own_depart)

    await deposit(
        "LEFT", "left_part", "left_source", "left_pad",
        "left_pickup_wait", "left_clear", "left_depart", "left_ready",
    )
    await deposit(
        "RIGHT", "right_part", "right_source", "right_pad",
        "right_pickup_wait", "right_clear", "right_depart", "right_ready",
    )
    await consume(
        "LEFT", "right_part", "right_pad", "left_pickup_wait",
        "left_target", "left_depart", "right_ready",
    )
    await consume(
        "RIGHT", "left_part", "left_pad", "right_pickup_wait",
        "right_target", "right_depart", "left_ready",
    )
