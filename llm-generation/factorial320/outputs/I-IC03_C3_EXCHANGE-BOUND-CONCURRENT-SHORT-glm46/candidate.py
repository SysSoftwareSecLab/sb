import asyncio

async def run_task(robot):
    # Helper to acquire resources in order
    async def acquire_resources(arm, resource_ids, timeout_s):
        for rid in resource_ids:
            await robot.acquire(arm, rid, timeout_s)

    # Helper to release resources in order
    async def release_resources(arm, resource_ids):
        for rid in resource_ids:
            await robot.release_resource(arm, rid)

    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TIMEOUT = 4.0
    
    # Resources
    RESOURCES = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    
    # Events
    EVT_LEFT_READY = "left_ready"
    EVT_RIGHT_READY = "right_ready"
    EVT_GATE = "rq2_gate"

    # Poses
    LEFT_HOME = "left_home"
    LEFT_SOURCE = "left_source"
    LEFT_PAD = "left_pad"
    LEFT_TARGET = "left_target"
    LEFT_DEPART = "left_depart"
    
    RIGHT_HOME = "right_home"
    RIGHT_SOURCE = "right_source"
    RIGHT_PAD = "right_pad"
    RIGHT_TARGET = "right_target"
    RIGHT_DEPART = "right_depart"
    
    LEFT_PICKUP_WAIT = "left_pickup_wait"
    RIGHT_PICKUP_WAIT = "right_pickup_wait"

    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"

    # 1. Acquire resources with LEFT arm
    await acquire_resources(LEFT, RESOURCES, TIMEOUT)

    # 2. Signal rq2_gate
    gate_receipt = robot.signal(EVT_GATE)

    # 3. Wait for rq2_gate
    # Note: wait_event requires timeout_s
    await robot.wait_event(EVT_GATE, TIMEOUT)

    # 4. Define the concurrent dual-arm mission
    async def left_mission():
        # Deposit own part
        await robot.move(LEFT, LEFT_SOURCE)
        await robot.grasp(LEFT, LEFT_PART)
        await robot.move(LEFT, LEFT_PAD)
        await robot.release(LEFT, LEFT_PART, LEFT_PAD)
        # Immediate departure
        await robot.move(LEFT, LEFT_PICKUP_WAIT)
        
        # Signal ready
        robot.signal(EVT_LEFT_READY)
        
        # Wait for peer
        peer_receipt = await robot.wait_event(EVT_RIGHT_READY, TIMEOUT)
        
        # Consume peer item
        await robot.move(LEFT, RIGHT_PAD, receipt=peer_receipt)
        await robot.grasp(LEFT, RIGHT_PART)
        
        # Clear peer event
        robot.clear_event(EVT_RIGHT_READY, expected_version=peer_receipt.version)
        
        # Move to target
        await robot.move(LEFT, LEFT_TARGET)
        await robot.release(LEFT, RIGHT_PART, LEFT_TARGET)
        
        # Depart
        await robot.move(LEFT, LEFT_DEPART)

    async def right_mission():
        # Deposit own part
        await robot.move(RIGHT, RIGHT_SOURCE)
        await robot.grasp(RIGHT, RIGHT_PART)
        await robot.move(RIGHT, RIGHT_PAD)
        await robot.release(RIGHT, RIGHT_PART, RIGHT_PAD)
        # Immediate departure
        await robot.move(RIGHT, RIGHT_PICKUP_WAIT)
        
        # Signal ready
        robot.signal(EVT_RIGHT_READY)
        
        # Wait for peer
        peer_receipt = await robot.wait_event(EVT_LEFT_READY, TIMEOUT)
        
        # Consume peer item
        await robot.move(RIGHT, LEFT_PAD, receipt=peer_receipt)
        await robot.grasp(RIGHT, LEFT_PART)
        
        # Clear peer event
        robot.clear_event(EVT_LEFT_READY, expected_version=peer_receipt.version)
        
        # Move to target
        await robot.move(RIGHT, RIGHT_TARGET)
        await robot.release(RIGHT, LEFT_PART, RIGHT_TARGET)
        
        # Depart
        await robot.move(RIGHT, RIGHT_DEPART)

    # 5. Execute mission concurrently
    await asyncio.gather(left_mission(), right_mission())

    # 6. Clear rq2_gate
    robot.clear_event(EVT_GATE, expected_version=gate_receipt.version)

    # 7. Release resources
    await release_resources(LEFT, RESOURCES)
