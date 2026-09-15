import asyncio

async def run_task(robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Poses
    LEFT_HOME = "left_home"
    RIGHT_HOME = "right_home"
    LEFT_SOURCE = "left_source"
    RIGHT_SOURCE = "right_source"
    LEFT_PAD = "left_pad"
    RIGHT_PAD = "right_pad"
    LEFT_TARGET = "left_target"
    RIGHT_TARGET = "right_target"
    LEFT_DEPART = "left_depart"
    RIGHT_DEPART = "right_depart"
    LEFT_PICKUP_WAIT = "left_pickup_wait"
    RIGHT_PICKUP_WAIT = "right_pickup_wait"
    
    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    RQ2_GATE = "rq2_gate"
    
    # Resources
    RQ2_GAP_0 = "rq2_gap_0"
    RQ2_GAP_1 = "rq2_gap_1"
    RQ2_GAP_2 = "rq2_gap_2"
    
    # Timeout
    TIMEOUT = 30.0

    # --- RQ2_GATE Producer/Consumer Logic ---
    # "Signal rq2_gate exactly once, wait its exact active receipt exactly once, and clear exactly that version after its assigned protected scope."
    # "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    # "Keep rq2_gate active while executing the complete inherited dual-arm mission after the wait; clear only after the mission."
    # "Use joined concurrent scheduling for both the inherited dual-arm mission and the rq2_gate producer/consumer."
    
    async def rq2_producer():
        # Signal the gate
        robot.signal(RQ2_GATE)
        
        # Acquire and release resources 0, 1, 2 in numeric order with LEFT
        # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order; never retain them at return."
        # "complete all three rq2_gap resource checks"
        # Assuming "check" means acquire/release cycle.
        # Note: LEFT arm is also used in the main mission. 
        # The mission requires LEFT to move to left_pad, then wait, then move to right_pad.
        # This logic must interleave or run concurrently. 
        # Given "joined concurrent scheduling", we run this as a task.
        # However, LEFT arm cannot be in two places at once.
        # The resource checks are likely lightweight or the main mission waits for RIGHT_READY.
        # Let's execute the resource checks sequentially on LEFT.
        
        # We must ensure we don't conflict with the main mission's use of LEFT.
        # Main mission LEFT: Home -> Source -> Pad -> Wait -> PickupWait -> Pad -> Target -> Depart.
        # The resource checks must fit in the gaps or be interleaved.
        # Since the prompt asks for "joined concurrent scheduling", we assume the scheduler handles the arm contention or we structure it to fit.
        # Given the strict ordering of the main mission, we will run the resource checks in the background.
        # If the main mission blocks LEFT, this will wait.
        
        await robot.acquire(LEFT, RQ2_GAP_0, TIMEOUT)
        await robot.release_resource(LEFT, RQ2_GAP_0)
        
        await robot.acquire(LEFT, RQ2_GAP_1, TIMEOUT)
        await robot.release_resource(LEFT, RQ2_GAP_1)
        
        await robot.acquire(LEFT, RQ2_GAP_2, TIMEOUT)
        await robot.release_resource(LEFT, RQ2_GAP_2)

    async def rq2_consumer():
        # Wait for the gate
        receipt = await robot.wait_event(RQ2_GATE, TIMEOUT)
        return receipt

    # Start the producer task
    producer_task = asyncio.create_task(rq2_producer())
    
    # --- Main Mission (Inherited Dual-Arm Exchange) ---
    # Variant B: "gather two workers; each worker deposits, waits for peer, then consumes."
    
    async def left_worker():
        # 1. Deposit own item (left_part) on own pad (left_pad)
        # Move Home -> Source
        await robot.move(LEFT, LEFT_SOURCE)
        # Grasp
        await robot.grasp(LEFT, LEFT_PART)
        # Move Source -> Pad
        await robot.move(LEFT, LEFT_PAD)
        # Release
        await robot.release(LEFT, LEFT_PART, LEFT_PAD)
        # "immediately clears the pad"
        await robot.move(LEFT, LEFT_DEPART) # Depart clears the pad area
        
        # 2. Wait for peer ready (RIGHT_READY)
        # "Before an arm picks up the peer item, both own deposit/clear and a wait for peer ready must have completed."
        peer_ready_receipt = await robot.wait_event(RIGHT_READY, TIMEOUT)
        
        # 3. Consume peer item (right_part) from peer pad (right_pad)
        # Move to pickup wait pose
        await robot.move(LEFT, LEFT_PICKUP_WAIT)
        # Move to pad (approach)
        await robot.move(LEFT, RIGHT_PAD)
        # Grasp
        await robot.grasp(LEFT, RIGHT_PART)
        
        # 4. Transport to own target (left_target)
        # "The carried move to its own target must carry the exact active peer-item receipt returned by wait"
        await robot.move(LEFT, LEFT_TARGET, receipt=peer_ready_receipt)
        
        # Release
        await robot.release(LEFT, RIGHT_PART, LEFT_TARGET)
        
        # Depart
        await robot.move(LEFT, LEFT_DEPART)
        
        # 5. Publish own ready event (LEFT_READY)
        # "immediately clears the pad before publishing its own item-bound ready event."
        # Already cleared pad by moving to depart.
        robot.signal(LEFT_READY, item_id=LEFT_PART)

    async def right_worker():
        # 1. Deposit own item (right_part) on own pad (right_pad)
        await robot.move(RIGHT, RIGHT_SOURCE)
        await robot.grasp(RIGHT, RIGHT_PART)
        await robot.move(RIGHT, RIGHT_PAD)
        await robot.release(RIGHT, RIGHT_PART, RIGHT_PAD)
        await robot.move(RIGHT, RIGHT_DEPART)
        
        # 2. Wait for peer ready (LEFT_READY)
        peer_ready_receipt = await robot.wait_event(LEFT_READY, TIMEOUT)
        
        # 3. Consume peer item (left_part) from peer pad (left_pad)
        await robot.move(RIGHT, RIGHT_PICKUP_WAIT)
        await robot.move(RIGHT, LEFT_PAD)
        await robot.grasp(RIGHT, LEFT_PART)
        
        # 4. Transport to own target (right_target)
        await robot.move(RIGHT, RIGHT_TARGET, receipt=peer_ready_receipt)
        
        await robot.release(RIGHT, LEFT_PART, RIGHT_TARGET)
        await robot.move(RIGHT, RIGHT_DEPART)
        
        # 5. Publish own ready event (RIGHT_READY)
        robot.signal(RIGHT_READY, item_id=RIGHT_PART)

    # Run workers concurrently
    left_task = asyncio.create_task(left_worker())
    right_task = asyncio.create_task(right_worker())
    
    # Wait for workers to finish
    await left_task
    await right_task
    
    # --- RQ2_GATE Completion ---
    # "complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    # We started the producer (which does checks) and the workers.
    # We must ensure producer is done before we wait/consume?
    # The text says: "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    # This implies the wait happens AFTER the checks.
    # Since the workers are done, we can now ensure the producer is done and then wait.
    await producer_task
    
    # Now wait for the gate (Consumer part)
    # "wait its exact active receipt exactly once"
    gate_receipt = await robot.wait_event(RQ2_GATE, TIMEOUT)
    
    # "clear exactly that version after its assigned protected scope."
    # "Keep rq2_gate active while executing the complete inherited dual-arm mission after the wait"
    # The mission is done. Scope is over. Clear it.
    robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)
