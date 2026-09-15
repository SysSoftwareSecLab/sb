import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_WAIT = "left_wait"
    RIGHT_HOME = "right_home"
    RIGHT_WAIT = "right_wait"
    
    SOURCE_0 = "source_0"
    SOURCE_1 = "source_1"
    BUFFER_0 = "buffer_0"
    BUFFER_1 = "buffer_1"
    TARGET_0 = "target_0"
    TARGET_1 = "target_1"
    
    # Items
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    # Resources
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    RQ2_GAP_0 = "rq2_gap_0"
    RQ2_GAP_1 = "rq2_gap_1"
    RQ2_GAP_2 = "rq2_gap_2"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    RQ2_GATE = "rq2_gate"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"

    async def acquire_gaps():
        # Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order
        await robot.acquire(LEFT, RQ2_GAP_0, 120)
        await robot.release_resource(LEFT, RQ2_GAP_0)
        
        await robot.acquire(LEFT, RQ2_GAP_1, 120)
        await robot.release_resource(LEFT, RQ2_GAP_1)
        
        await robot.acquire(LEFT, RQ2_GAP_2, 120)
        await robot.release_resource(LEFT, RQ2_GAP_2)

    # 1. Complete all three rq2_gap resource checks before signalling rq2_gate
    await acquire_gaps()
    
    # 2. Signal rq2_gate exactly once
    gate_receipt = robot.signal(RQ2_GATE)
    
    # 3. Wait its exact active receipt exactly once
    # "wait immediately after the signal"
    await robot.wait_event(RQ2_GATE, 120)
    
    # 4. Keep rq2_gate active while executing the complete inherited dual-arm mission after the wait
    # Use joined concurrent scheduling for both the inherited dual-arm mission and the rq2_gate producer/consumer.
    
    async def producer_part_0():
        # LEFT owns tool from before each source pickup through ready publication
        await robot.acquire(LEFT, TOOL, 120)
        
        # Approach source_0
        await robot.move(LEFT, SOURCE_0)
        # Grasp part_0
        await robot.grasp(LEFT, PART_0)
        
        # Both participants own buffer_lock during buffer entry and departure
        await robot.acquire(LEFT, BUFFER_LOCK, 120)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_0)
        
        # Release part_0 at buffer
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # Depart immediately
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Publish ready_0
        ready_0_receipt = robot.signal(READY_0)
        
        # Release tool on every exit
        await robot.release_resource(LEFT, TOOL)
        
        return ready_0_receipt

    async def consumer_part_0(ready_receipt: EventReceipt):
        # Wait the corresponding ready receipt before pickup
        # (Already passed in as active receipt)
        
        # Both participants own buffer_lock during buffer entry and departure
        await robot.acquire(RIGHT, BUFFER_LOCK, 120)
        
        # Approach buffer_0
        await robot.move(RIGHT, BUFFER_0)
        
        # Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # Depart immediately
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Supplies that exact active item receipt on carried move to target
        await robot.move(RIGHT, TARGET_0, receipt=ready_receipt)
        
        # Consumer clears ready after its carried move
        robot.clear_event(READY_0, expected_version=ready_receipt.version)
        
        # Release on target
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # Depart before publishing empty_0
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Publish empty_0
        robot.signal(EMPTY_0)

    async def producer_part_1():
        # Producer waits and clears empty_0 before entering buffer with the second part
        empty_0_receipt = await robot.wait_event(EMPTY_0, 120)
        robot.clear_event(EMPTY_0, expected_version=empty_0_receipt.version)
        
        # For item 1, wait and clear empty_0, then inspect both readiness facts
        # C7 checks serially and C8 joins the two checks inside the loop branch.
        # We inspect both facts.
        await robot.inspect(LEFT, FACT_LINE_CLEAR)
        await robot.inspect(LEFT, FACT_RECEIVER_READY)
        
        # LEFT owns tool
        await robot.acquire(LEFT, TOOL, 120)
        
        # Approach source_1
        await robot.move(LEFT, SOURCE_1)
        # Grasp part_1
        await robot.grasp(LEFT, PART_1)
        
        # Acquire buffer_lock
        await robot.acquire(LEFT, BUFFER_LOCK, 120)
        
        # Move to buffer
        await robot.move(LEFT, BUFFER_1)
        
        # Release part_1
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # Depart immediately
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Publish ready_1
        ready_1_receipt = robot.signal(READY_1)
        
        # Release tool
        await robot.release_resource(LEFT, TOOL)
        
        return ready_1_receipt

    async def consumer_part_1(ready_receipt: EventReceipt):
        # Wait ready receipt
        # (Passed in)
        
        # Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, 120)
        
        # Approach buffer_1
        await robot.move(RIGHT, BUFFER_1)
        
        # Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # Depart
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Move to target with receipt
        await robot.move(RIGHT, TARGET_1, receipt=ready_receipt)
        
        # Clear ready
        robot.clear_event(READY_1, expected_version=ready_receipt.version)
        
        # Release
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # Depart
        await robot.move(RIGHT, RIGHT_HOME)

    # Concurrent execution
    # Episode 1
    p0_task = asyncio.create_task(producer_part_0())
    r0_receipt = await p0_task
    c0_task = asyncio.create_task(consumer_part_0(r0_receipt))
    
    # Episode 2
    # B runs producer and consumer coroutines together.
    # We can start consumer for part 1 only after part 0 is done (RIGHT arm busy).
    # We can start producer for part 1 after empty_0 is cleared (which happens inside consumer_part_0).
    # So we await consumer_part_0 first.
    await c0_task
    
    p1_task = asyncio.create_task(producer_part_1())
    r1_receipt = await p1_task
    c1_task = asyncio.create_task(consumer_part_1(r1_receipt))
    await c1_task
    
    # 5. Clear rq2_gate exactly that version after its assigned protected scope
    robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)
