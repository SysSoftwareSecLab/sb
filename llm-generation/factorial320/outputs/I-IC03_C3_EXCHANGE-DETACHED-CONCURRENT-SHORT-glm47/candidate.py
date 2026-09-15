import asyncio

async def run_task(robot):
    # --- RQ2_GATE PROTOCOL ---
    # Acquire resources rq2_gap_0, rq2_gap_1, rq2_gap_2 with LEFT arm in numeric order.
    # Timeout 4s is safe within the 30s deadline.
    await robot.acquire("LEFT", "rq2_gap_0", 4.0)
    await robot.acquire("LEFT", "rq2_gap_1", 4.0)
    await robot.acquire("LEFT", "rq2_gap_2", 4.0)

    # Signal rq2_gate exactly once.
    gate_receipt = robot.signal("rq2_gate")

    # Wait immediately after the signal for the exact active receipt.
    # Timeout 4s is safe.
    await robot.wait_event("rq2_gate", 4.0)

    # Clear the event using the version from the receipt.
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # Release resources in numeric order (or any order, but numeric is consistent).
    await robot.release_resource("LEFT", "rq2_gap_0")
    await robot.release_resource("LEFT", "rq2_gap_1")
    await robot.release_resource("LEFT", "rq2_gap_2")

    # --- DUAL-ARM EXCHANGE MISSION ---
    # Define the concurrent worker for each arm.
    # Variant B: Each worker deposits, waits for peer, then consumes.
    async def arm_worker(arm_name, my_part, my_source, my_pad, my_target, my_depart, 
                         peer_ready_event, my_ready_event, peer_pad, peer_part):
        
        # 1. Deposit own part
        # Move to source (Approach sequence start)
        await robot.move(arm_name, my_source)
        # Grasp own part
        await robot.grasp(arm_name, my_part)
        # Move to pad
        await robot.move(arm_name, my_pad)
        # Release own part
        await robot.release(arm_name, my_part, my_pad)
        # Immediate departure (clear the pad)
        await robot.move(arm_name, my_depart)

        # 2. Signal own ready event
        my_ready_receipt = robot.signal(my_ready_event)

        # 3. Wait for peer ready event
        peer_ready_receipt = await robot.wait_event(peer_ready_event, 4.0)

        # 4. Consume peer item
        # Move to pickup wait pose (Approach sequence start for peer part)
        pickup_wait_pose = f"{arm_name.lower()}_pickup_wait"
        await robot.move(arm_name, pickup_wait_pose)
        # Grasp peer part
        await robot.grasp(arm_name, peer_part)
        # Move to own target carrying the peer item receipt
        await robot.move(arm_name, my_target, receipt=peer_ready_receipt)
        # Release peer part
        await robot.release(arm_name, peer_part, my_target)
        # Move to final departure
        await robot.move(arm_name, my_depart)

        # 5. Clear own ready event
        robot.clear_event(my_ready_event, expected_version=my_ready_receipt.version)

    # Create tasks for LEFT and RIGHT arms
    left_task = asyncio.create_task(arm_worker(
        "LEFT", 
        "left_part", "left_source", "left_pad", "left_target", "left_depart",
        "right_ready", "left_ready", "right_pad", "right_part"
    ))

    right_task = asyncio.create_task(arm_worker(
        "RIGHT", 
        "right_part", "right_source", "right_pad", "right_target", "right_depart",
        "left_ready", "right_ready", "left_pad", "left_part"
    ))

    # Wait for both tasks to complete
    await left_task
    await right_task
