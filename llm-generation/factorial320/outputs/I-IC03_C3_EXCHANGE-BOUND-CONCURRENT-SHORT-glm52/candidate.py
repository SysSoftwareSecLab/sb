import asyncio

async def run_task(robot):
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    async def acquire_gap(idx):
        rid = f"rq2_gap_{idx}"
        await robot.acquire(LEFT, rid, 5)
        return rid

    async def release_gap(rid):
        await robot.release_resource(LEFT, rid)

    async def left_worker():
        # Deposit left_part on left_pad
        await robot.move(LEFT, "left_source")
        await robot.grasp(LEFT, "left_part")
        await robot.move(LEFT, "left_pad")
        await robot.release(LEFT, "left_part", "left_pad")
        await robot.move(LEFT, "left_clear")
        # Publish left_ready
        left_ready_receipt = robot.signal("left_ready", "left_part")
        # Wait for peer ready before consuming peer item
        right_ready_receipt = await robot.wait_event("right_ready", 30)
        # Consume right_part: carry move uses exact active peer-item receipt
        await robot.move(LEFT, "left_pickup_wait")
        await robot.grasp(LEFT, "right_part")
        await robot.move(LEFT, "right_target", receipt=right_ready_receipt)
        robot.clear_event("right_ready", expected_version=right_ready_receipt.version)
        await robot.move(LEFT, "left_depart")

    async def right_worker():
        # Deposit right_part on right_pad
        await robot.move(RIGHT, "right_source")
        await robot.grasp(RIGHT, "right_part")
        await robot.move(RIGHT, "right_pad")
        await robot.release(RIGHT, "right_part", "right_pad")
        await robot.move(RIGHT, "right_clear")
        # Publish right_ready
        right_ready_receipt = robot.signal("right_ready", "right_part")
        # Wait for peer ready before consuming peer item
        left_ready_receipt = await robot.wait_event("left_ready", 30)
        # Consume left_part: carry move uses exact active peer-item receipt
        await robot.move(RIGHT, "right_pickup_wait")
        await robot.grasp(RIGHT, "left_part")
        await robot.move(RIGHT, "left_target", receipt=left_ready_receipt)
        robot.clear_event("left_ready", expected_version=left_ready_receipt.version)
        await robot.move(RIGHT, "right_depart")

    async def gap_producer():
        # Acquire rq2_gap_0,1,2 once each with LEFT in numeric order
        r0 = await acquire_gap(0)
        r1 = await acquire_gap(1)
        r2 = await acquire_gap(2)
        # Release them before signalling rq2_gate; never retain at return
        await release_gap(r2)
        await release_gap(r1)
        await release_gap(r0)
        # Signal rq2_gate exactly once
        gate_receipt = robot.signal("rq2_gate")
        return gate_receipt

    async def gate_consumer(gate_receipt):
        # Wait rq2_gate's exact active receipt exactly once
        waited = await robot.wait_event("rq2_gate", 30)
        # Keep rq2_gate active while executing complete inherited dual-arm mission
        await asyncio.gather(left_worker(), right_worker())
        # Clear rq2_gate only after the mission
        robot.clear_event("rq2_gate", expected_version=waited.version)

    gate_receipt = await gap_producer()
    await gate_consumer(gate_receipt)
