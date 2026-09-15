import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    
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
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    RQ2_GATE = "rq2_gate"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"
    
    # Timeout
    TIMEOUT_S = 4.0

    # Helper to clear event
    def clear_event_sync(event_id: str, receipt: EventReceipt):
        robot.clear_event(event_id, expected_version=receipt.version)

    # --- Episode 0: part_0 ---
    
    # Producer (LEFT) for part_0
    async def producer_0():
        # Acquire tool
        await robot.acquire(LEFT, TOOL, TIMEOUT_S)
        
        # Move to source_0 (Approach)
        await robot.move(LEFT, SOURCE_0, timeout_s=TIMEOUT_S)
        
        # Grasp part_0
        await robot.grasp(LEFT, PART_0)
        
        # Acquire buffer_lock
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        
        # Move to buffer_0
        await robot.move(LEFT, BUFFER_0, timeout_s=TIMEOUT_S)
        
        # Release part_0 at buffer_0
        await robot.release(LEFT, PART_0, BUFFER_0)
        
        # Depart buffer (Immediate departure)
        await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_S)
        
        # Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Release tool
        await robot.release_resource(LEFT, TOOL)
        
        # Signal ready_0
        receipt = robot.signal(READY_0, item_id=PART_0)
        return receipt

    # Consumer (RIGHT) for part_0
    async def consumer_0():
        # Wait for ready_0
        ready_receipt = await robot.wait_event(READY_0, TIMEOUT_S)
        
        # Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # Move to buffer_0 (Approach)
        await robot.move(RIGHT, BUFFER_0, timeout_s=TIMEOUT_S)
        
        # Grasp part_0
        await robot.grasp(RIGHT, PART_0)
        
        # Depart buffer (Immediate departure)
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Move to target_0 with receipt
        await robot.move(RIGHT, TARGET_0, timeout_s=TIMEOUT_S, receipt=ready_receipt)
        
        # Clear ready_0
        clear_event_sync(READY_0, ready_receipt)
        
        # Release part_0 at target_0
        await robot.release(RIGHT, PART_0, TARGET_0)
        
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # Signal empty_0
        robot.signal(EMPTY_0)

    # Run Episode 0
    await asyncio.gather(producer_0(), consumer_0())

    # --- Episode 1: part_1 ---
    
    # Wait for empty_0 before proceeding with producer
    empty_receipt = await robot.wait_event(EMPTY_0, TIMEOUT_S)
    clear_event_sync(EMPTY_0, empty_receipt)
    
    # Inspect facts (Serial check)
    obs_line = await robot.inspect(LEFT, FACT_LINE_CLEAR)
    obs_recv = await robot.inspect(LEFT, FACT_RECEIVER_READY)
    
    # Producer (LEFT) for part_1
    async def producer_1():
        # Acquire tool
        await robot.acquire(LEFT, TOOL, TIMEOUT_S)
        
        # Move to source_1 (Approach)
        await robot.move(LEFT, SOURCE_1, timeout_s=TIMEOUT_S)
        
        # Grasp part_1
        await robot.grasp(LEFT, PART_1)
        
        # Acquire buffer_lock
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        
        # Move to buffer_1
        await robot.move(LEFT, BUFFER_1, timeout_s=TIMEOUT_S)
        
        # Release part_1 at buffer_1
        await robot.release(LEFT, PART_1, BUFFER_1)
        
        # Depart buffer
        await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_S)
        
        # Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Release tool
        await robot.release_resource(LEFT, TOOL)
        
        # Signal ready_1
        receipt = robot.signal(READY_1, item_id=PART_1)
        return receipt

    # Consumer (RIGHT) for part_1
    async def consumer_1():
        # Wait for ready_1
        ready_receipt = await robot.wait_event(READY_1, TIMEOUT_S)
        
        # Acquire buffer_lock
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        
        # Move to buffer_1 (Approach)
        await robot.move(RIGHT, BUFFER_1, timeout_s=TIMEOUT_S)
        
        # Grasp part_1
        await robot.grasp(RIGHT, PART_1)
        
        # Depart buffer
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Move to target_1 with receipt
        await robot.move(RIGHT, TARGET_1, timeout_s=TIMEOUT_S, receipt=ready_receipt)
        
        # Clear ready_1
        clear_event_sync(READY_1, ready_receipt)
        
        # Release part_1 at target_1
        await robot.release(RIGHT, PART_1, TARGET_1)
        
        # Depart target
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        
        # Signal empty_0
        robot.signal(EMPTY_0)

    # Run Episode 1
    await asyncio.gather(producer_1(), consumer_1())

    # --- RQ2 Gate Loop ---
    
    # Loop structure: FOR -> PAR_JOIN -> consumer IF
    # We run one finite iteration as implied by the task structure description.
    
    # Define RQ2 Producer
    async def rq2_producer():
        # Signal rq2_gate
        receipt = robot.signal(RQ2_GATE)
        return receipt

    # Define RQ2 Consumer
    async def rq2_consumer():
        # Wait for exact active receipt
        gate_receipt = await robot.wait_event(RQ2_GATE, TIMEOUT_S)
        
        # Execute complete inherited mission (Episode 0 logic)
        # Re-using the logic defined in Episode 0
        
        # Acquire tool
        await robot.acquire(LEFT, TOOL, TIMEOUT_S)
        await robot.move(LEFT, SOURCE_0, timeout_s=TIMEOUT_S)
        await robot.grasp(LEFT, PART_0)
        await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
        await robot.move(LEFT, BUFFER_0, timeout_s=TIMEOUT_S)
        await robot.release(LEFT, PART_0, BUFFER_0)
        await robot.move(LEFT, LEFT_HOME, timeout_s=TIMEOUT_S)
        await robot.release_resource(LEFT, BUFFER_LOCK)
        await robot.release_resource(LEFT, TOOL)
        prod_receipt = robot.signal(READY_0, item_id=PART_0)
        
        # Consumer side
        cons_receipt = await robot.wait_event(READY_0, TIMEOUT_S)
        await robot.acquire(RIGHT, BUFFER_LOCK, TIMEOUT_S)
        await robot.move(RIGHT, BUFFER_0, timeout_s=TIMEOUT_S)
        await robot.grasp(RIGHT, PART_0)
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        await robot.move(RIGHT, TARGET_0, timeout_s=TIMEOUT_S, receipt=cons_receipt)
        clear_event_sync(READY_0, cons_receipt)
        await robot.release(RIGHT, PART_0, TARGET_0)
        await robot.move(RIGHT, RIGHT_HOME, timeout_s=TIMEOUT_S)
        robot.signal(EMPTY_0)
        
        # Clear rq2_gate version
        clear_event_sync(RQ2_GATE, gate_receipt)

    # Concurrently join producer and consumer
    await asyncio.gather(rq2_producer(), rq2_consumer())

    # Final state: rq2_gate inactive at return is ensured by clear_event_sync.
