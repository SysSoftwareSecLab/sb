import asyncio

from bridge_robot_api import Robot


async def _rq2_gate_protocol(robot: Robot) -> None:
    """Acquire/release rq2_gap_0..2 in numeric order, then signal/wait/clear rq2_gate."""
    for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", resource_id, 5)
        await robot.release_resource("LEFT", resource_id)

    gate_receipt = robot.signal("rq2_gate")
    await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)


async def _left_arm(robot: Robot, right_ready_receipt: asyncio.Future) -> None:
    """LEFT deposits left_part on left_pad, waits for RIGHT ready, then consumes right_part."""
    # Approach left_part from left_home and grasp immediately.
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")

    # Deposit own part on own pad.
    await robot.move("LEFT", "left_pad")
    await robot.release("LEFT", "left_part", "left_pad")
    await robot.move("LEFT", "left_clear")

    # Publish own ready event.
    left_receipt = robot.signal("left_ready")
    right_ready_receipt.set_result(left_receipt)

    # Wait for peer ready before consuming peer item.
    peer_receipt = await robot.wait_event("right_ready", 30)

    # Move to pickup wait, approach peer item, grasp, carry to own target.
    await robot.move("LEFT", "left_pickup_wait")
    await robot.move("LEFT", "right_pad", receipt=peer_receipt)
    await robot.grasp("LEFT", "right_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "right_part", "left_target")

    # Depart and clear the peer-item receipt after the carrying move completed.
    await robot.move("LEFT", "left_depart")
    robot.clear_event("right_ready", expected_version=peer_receipt.version)


async def _right_arm(robot: Robot, left_ready_receipt: asyncio.Future) -> None:
    """RIGHT deposits right_part on right_pad, waits for LEFT ready, then consumes left_part."""
    # Approach right_part from right_home and grasp immediately.
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")

    # Deposit own part on own pad.
    await robot.move("RIGHT", "right_pad")
    await robot.release("RIGHT", "right_part", "right_pad")
    await robot.move("RIGHT", "right_clear")

    # Publish own ready event.
    right_receipt = robot.signal("right_ready")
    left_ready_receipt.set_result(right_receipt)

    # Wait for peer ready before consuming peer item.
    peer_receipt = await robot.wait_event("left_ready", 30)

    # Move to pickup wait, approach peer item, grasp, carry to own target.
    await robot.move("RIGHT", "right_pickup_wait")
    await robot.move("RIGHT", "left_pad", receipt=peer_receipt)
    await robot.grasp("RIGHT", "left_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "left_part", "right_target")

    # Depart and clear the peer-item receipt after the carrying move completed.
    await robot.move("RIGHT", "right_depart")
    robot.clear_event("left_ready", expected_version=peer_receipt.version)


async def run_task(robot: Robot) -> None:
    loop = asyncio.get_running_loop()
    left_ready_receipt: asyncio.Future = loop.create_future()
    right_ready_receipt: asyncio.Future = loop.create_future()

    async def _inherited_mission() -> None:
        await asyncio.gather(
            _left_arm(robot, right_ready_receipt),
            _right_arm(robot, left_ready_receipt),
        )

    await asyncio.gather(
        _rq2_gate_protocol(robot),
        _inherited_mission(),
    )
