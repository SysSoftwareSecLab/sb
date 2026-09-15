async def run_task(robot):
    # Phase 1: rq2_gate protocol — acquire rq2_gap_0/1/2 with LEFT in order, OFF only.
    for i in range(3):
        await robot.acquire("LEFT", f"rq2_gap_{i}", 5)
        await robot.release_resource("LEFT", f"rq2_gap_{i}")

    gate_receipt = robot.signal("rq2_gate")
    gate_wait = await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_wait.version)

    # Phase 2: concurrent dual-arm exchange via two workers.
    import asyncio

    async def worker(arm, my_part, my_source, my_pad, my_depart,
                     peer_part, peer_pad, my_pickup_wait, my_ready, peer_ready):
        # Deposit own part on own pad.
        await robot.move(arm, my_source)
        grasp_obs = await robot.grasp(arm, my_part)
        await robot.move(arm, my_pad)
        await robot.release(arm, my_part, my_pad)
        await robot.move(arm, my_pickup_wait)
        # Publish own ready event.
        robot.signal(my_ready)
        # Wait for peer ready before consuming peer item.
        peer_receipt = await robot.wait_event(peer_ready, 30)
        # Move to peer pad carrying the active peer-item receipt.
        await robot.move(arm, peer_pad, receipt=peer_receipt)
        # Clear that event after the carried move completes.
        robot.clear_event(peer_ready, expected_version=peer_receipt.version)
        # Grasp peer item and deliver to own target.
        await robot.grasp(arm, peer_part)
        await robot.move(arm, my_depart)
        await robot.release(arm, peer_part, my_depart)

    left_worker = worker(
        "LEFT", "left_part", "left_source", "left_pad", "left_depart",
        "right_part", "right_pad", "left_pickup_wait", "left_ready", "right_ready",
    )
    right_worker = worker(
        "RIGHT", "right_part", "right_source", "right_pad", "right_depart",
        "left_part", "left_pad", "right_pickup_wait", "right_ready", "left_ready",
    )
    await asyncio.gather(left_worker, right_worker)
