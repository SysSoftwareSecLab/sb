import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- rq2_gate protocol (producer side) ----
    gate_receipt = robot.signal("rq2_gate")

    # ---- rq2_gap_0/1/2 resource checks with LEFT, numeric order ----
    for idx in range(3):
        resource_id = f"rq2_gap_{idx}"
        await robot.acquire("LEFT", resource_id, 5)
        await robot.release_resource("LEFT", resource_id)

    # ---- consume rq2_gate exactly once, then clear that exact version ----
    gate_wait = await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_wait.version)

    # ---- inherited dual-arm exchange mission (variant B: two workers) ----
    await asyncio.gather(
        _worker_left(robot, gate_receipt),
        _worker_right(robot, gate_receipt),
    )


async def _worker_left(robot: Robot, gate_receipt) -> None:
    arm = "LEFT"
    own_part = "left_part"
    own_pad = "left_pad"
    own_clear = "left_clear"
    own_depart = "left_depart"
    own_ready = "left_ready"
    peer_part = "right_part"
    peer_pad = "right_pad"
    peer_pickup_wait = "left_pickup_wait"
    peer_target = "right_target"
    peer_ready = "right_ready"

    # Deposit own part on own pad, then immediately clear the pad.
    await robot.move(arm, own_pad)
    await robot.release(arm, own_part, own_pad)
    await robot.move(arm, own_clear)
    left_ready_receipt = robot.signal(own_ready)

    # Before picking up peer item: wait for peer ready.
    right_ready_receipt = await robot.wait_event(peer_ready, 30)

    # Move to peer pickup wait, then approach+grasp peer item immediately.
    await robot.move(arm, peer_pickup_wait)
    await robot.move(arm, peer_pad, receipt=right_ready_receipt)
    await robot.grasp(arm, peer_part)

    # Carry peer item to own target, then clear peer ready event after move.
    await robot.move(arm, peer_target, receipt=right_ready_receipt)
    robot.clear_event(peer_ready, expected_version=right_ready_receipt.version)

    # Release peer item on own target and depart.
    await robot.release(arm, peer_part, peer_target)
    await robot.move(arm, own_depart)

    # Clear own ready event after its assigned protected scope.
    robot.clear_event(own_ready, expected_version=left_ready_receipt.version)


async def _worker_right(robot: Robot, gate_receipt) -> None:
    arm = "RIGHT"
    own_part = "right_part"
    own_pad = "right_pad"
    own_clear = "right_clear"
    own_depart = "right_depart"
    own_ready = "right_ready"
    peer_part = "left_part"
    peer_pad = "left_pad"
    peer_pickup_wait = "right_pickup_wait"
    peer_target = "left_target"
    peer_ready = "left_ready"

    # Deposit own part on own pad, then immediately clear the pad.
    await robot.move(arm, own_pad)
    await robot.release(arm, own_part, own_pad)
    await robot.move(arm, own_clear)
    right_ready_receipt = robot.signal(own_ready)

    # Before picking up peer item: wait for peer ready.
    left_ready_receipt = await robot.wait_event(peer_ready, 30)

    # Move to peer pickup wait, then approach+grasp peer item immediately.
    await robot.move(arm, peer_pickup_wait)
    await robot.move(arm, peer_pad, receipt=left_ready_receipt)
    await robot.grasp(arm, peer_part)

    # Carry peer item to own target, then clear peer ready event after move.
    await robot.move(arm, peer_target, receipt=left_ready_receipt)
    robot.clear_event(peer_ready, expected_version=left_ready_receipt.version)

    # Release peer item on own target and depart.
    await robot.release(arm, peer_part, peer_target)
    await robot.move(arm, own_depart)

    # Clear own ready event after its assigned protected scope.
    robot.clear_event(own_ready, expected_version=right_ready_receipt.version)
