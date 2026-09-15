import asyncio

async def run_task(robot):
    # Constants from PUBLIC TASK
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
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

    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    RQ2_GATE = "rq2_gate"

    # Timeout
    TIMEOUT = 30.0

    # --- Helper Functions ---

    async def deposit_and_signal(arm, part, source, pad, ready_event_id):
        # 1. Move to source (Approach)
        await robot.move(arm, source, timeout_s=TIMEOUT)
        # 2. Grasp
        await robot.grasp(arm, part)
        # 3. Move to pad
        await robot.move(arm, pad, timeout_s=TIMEOUT)
        # 4. Release
        await robot.release(arm, part, pad)
        # 5. Depart immediately (clear pad)
        depart_pose = LEFT_DEPART if arm == LEFT else RIGHT_DEPART
        await robot.move(arm, depart_pose, timeout_s=TIMEOUT)
        # 6. Signal ready
        receipt = robot.signal(ready_event_id)
        return receipt

    async def consume_and_clear(arm, part, pad, target, depart_pose, ready_event_id, peer_ready_receipt):
        # 1. Wait for peer ready
        # Note: The task says "wait for peer ready". 
        # In the loop structure, we wait on the specific receipt passed in.
        # However, wait_event takes an event_id. 
        # We must wait for the event to be active.
        # Since we are in a loop, we wait for the event corresponding to the receipt version?
        # The API wait_event waits for an event to be active.
        # We wait for the peer's ready event.
        active_receipt = await robot.wait_event(ready_event_id, timeout_s=TIMEOUT)
        
        # 2. Move to pickup wait (Approach start)
        wait_pose = LEFT_PICKUP_WAIT if arm == LEFT else RIGHT_PICKUP_WAIT
        await robot.move(arm, wait_pose, timeout_s=TIMEOUT)
        
        # 3. Move to pad (Approach end)
        await robot.move(arm, pad, timeout_s=TIMEOUT)
        
        # 4. Grasp
        await robot.grasp(arm, part)
        
        # 5. Move to target (Carried move with receipt)
        # "The carried move to its own target must carry the exact active peer-item receipt returned by wait"
        await robot.move(arm, target, timeout_s=TIMEOUT, receipt=active_receipt)
        
        # 6. Release
        await robot.release(arm, part, target)
        
        # 7. Depart
        await robot.move(arm, depart_pose, timeout_s=TIMEOUT)
        
        # 8. Clear the peer ready event
        # "clear that event after that move"
        robot.clear_event(ready_event_id, expected_version=active_receipt.version)

    # --- Main Execution ---

    # Phase 1: Deposit both parts and signal readiness
    # "Each arm deposits its own part on its own pad and immediately clears the pad before publishing its own item-bound ready event."
    # "A: deposit LEFT then RIGHT"
    
    # Deposit Left
    await deposit_and_signal(LEFT, LEFT_PART, LEFT_SOURCE, LEFT_PAD, LEFT_READY)
    
    # Deposit Right
    await deposit_and_signal(RIGHT, RIGHT_PART, RIGHT_SOURCE, RIGHT_PAD, RIGHT_READY)

    # Phase 2: Exchange (Consume peer parts)
    # "Before an arm picks up the peer item, both own deposit/clear and a wait for peer ready must have completed."
    # Since we ran deposits sequentially, both are done.
    
    # "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
    # "Use the structural-OOD shape FOR -> PAR_JOIN -> consumer IF"
    
    # We need to perform the exchange.
    # Left consumes Right's part. Right consumes Left's part.
    # Both need to wait for the respective peer ready events.
    
    # We create a loop (finite, 1 iteration as per "one finite loop iteration" usually implies the structure, 
    # but here we have a specific exchange to do. The task says "Inside one finite loop iteration...").
    # We will run the loop once.
    
    for _ in range(1):
        # PAR_JOIN: Producer (rq2_gate) and Consumer (Mission)
        
        # Producer: Signal rq2_gate
        async def producer():
            robot.signal(RQ2_GATE)
            
        # Consumer: The complete inherited mission (Exchange)
        # "the consumer waits the exact active receipt, executes the complete inherited mission, then clears that version"
        # This implies the consumer waits for rq2_gate.
        # The "complete inherited mission" is the exchange of parts.
        
        async def consumer():
            # Wait for rq2_gate
            gate_receipt = await robot.wait_event(RQ2_GATE, timeout_s=TIMEOUT)
            
            # Execute Exchange
            # Left takes Right Part, Right takes Left Part
            # These can happen in parallel
            
            task_l = asyncio.create_task(
                consume_and_clear(
                    LEFT, RIGHT_PART, RIGHT_PAD, RIGHT_TARGET, LEFT_DEPART, RIGHT_READY, None
                )
            )
            
            task_r = asyncio.create_task(
                consume_and_clear(
                    RIGHT, LEFT_PART, LEFT_PAD, LEFT_TARGET, RIGHT_DEPART, LEFT_READY, None
                )
            )
            
            await task_l
            await task_r
            
            # Clear rq2_gate
            robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)
            
        # Join Producer and Consumer
        await asyncio.gather(producer(), consumer())

    # End state: Arms at depart, parts exchanged, events cleared.
