import asyncio

async def run_task(robot):
    # RQ2 Gate Protocol
    # 1. Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # 2. Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 with LEFT, in numeric order
    for res_id in ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]:
        await robot.acquire("LEFT", res_id, 120.0)
        await robot.release_resource("LEFT", res_id)
    
    # 3. Wait for rq2_gate (exact active receipt)
    await robot.wait_event("rq2_gate", 120.0)
    
    # 4. Clear rq2_gate (exact version)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # Inherited Dual-Arm Mission (Serial Schedule)
    # Episode 1: part_0
    # Producer (LEFT)
    await robot.move("LEFT", "left_home")
    await robot.move("LEFT", "source_0")
    obs_p0 = await robot.grasp("LEFT", "part_0")
    
    await robot.acquire("LEFT", "buffer_lock", 120.0)
    await robot.move("LEFT", "buffer_0")
    await robot.release("LEFT", "part_0", "buffer_0")
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")
    
    ready_0_receipt = robot.signal("ready_0")
    
    # Consumer (RIGHT)
    await robot.wait_event("ready_0", 120.0)
    
    await robot.acquire("RIGHT", "buffer_lock", 120.0)
    await robot.move("RIGHT", "buffer_0")
    await robot.grasp("RIGHT", "part_0")
    await robot.move("RIGHT", "target_0", receipt=ready_0_receipt)
    robot.clear_event("ready_0", expected_version=ready_0_receipt.version)
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")
    
    robot.signal("empty_0")

    # Episode 2: part_1
    # Producer (LEFT)
    await robot.wait_event("empty_0", 120.0)
    robot.clear_event("empty_0", expected_version=1) # Initial 0, signaled once -> 1
    
    await robot.move("LEFT", "left_wait")
    await robot.move("LEFT", "source_1")
    obs_p1 = await robot.grasp("LEFT", "part_1")
    
    await robot.acquire("LEFT", "buffer_lock", 120.0)
    await robot.move("LEFT", "buffer_1")
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")
    
    ready_1_receipt = robot.signal("ready_1")
    
    # Consumer (RIGHT)
    await robot.wait_event("ready_1", 120.0)
    
    await robot.acquire("RIGHT", "buffer_lock", 120.0)
    await robot.move("RIGHT", "buffer_1")
    await robot.grasp("RIGHT", "part_1")
    await robot.move("RIGHT", "target_1", receipt=ready_1_receipt)
    robot.clear_event("ready_1", expected_version=ready_1_receipt.version)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")
