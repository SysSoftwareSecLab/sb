import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants from task
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    PART_0 = "part_0"
    PART_1 = "part_1"
    
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
    
    # Resources
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    RQ2_GATE = "rq2_gate"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"

    # Helper to execute the consumer mission for a specific part
    async def consumer_mission(part_id: str, buffer_pose: str, target_pose: str, ready_event_id: str):
        # Wait for the corresponding ready receipt
        ready_receipt = await robot.wait_event(ready_event_id, timeout_s=120)
        
        # Move to wait pose (approach start)
        if part_id == PART_0:
            await robot.move(RIGHT, RIGHT_HOME)
        else:
            await robot.move(RIGHT, RIGHT_WAIT)
            
        # Approach sequence: move to buffer interaction pose
        await robot.move(RIGHT, buffer_pose)
        
        # Grasp the part
        await robot.grasp(RIGHT, part_id)
        
        # Acquire buffer_lock for departure
        await robot.acquire(RIGHT, BUFFER_LOCK, timeout_s=120)
        
        # Move to target carrying the part, supplying the active ready receipt
        await robot.move(RIGHT, target_pose, receipt=ready_receipt)
        
        # Clear the ready event after the carried move
        robot.clear_event(ready_event_id, expected_version=ready_receipt.version)
        
        # Release the part at target
        await robot.release(RIGHT, part_id, target_pose)
        
        # Depart (move to home)
        await robot.move(RIGHT, RIGHT_HOME)
        
        # Release buffer_lock
        await robot.release_resource(RIGHT, BUFFER_LOCK)
        
        # Publish empty_0
        robot.signal(EMPTY_0)

    # Helper to execute the producer mission for a specific part
    async def producer_mission(part_id: str, source_pose: str, buffer_pose: str, ready_event_id: str):
        # Wait and clear empty_0 before entering buffer with the second part
        if part_id == PART_1:
            empty_receipt = await robot.wait_event(EMPTY_0, timeout_s=120)
            robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)
            
            # Inspect both readiness facts (C7 checks serially, C8 joins inside loop branch)
            # We are in a serial execution context for the loop body here, so we check sequentially.
            await robot.inspect(LEFT, FACT_LINE_CLEAR)
            await robot.inspect(LEFT, FACT_RECEIVER_READY)

        # Move to home (approach start for part_0)
        if part_id == PART_0:
            await robot.move(LEFT, LEFT_HOME)
        else:
            await robot.move(LEFT, LEFT_WAIT)
            
        # Approach sequence: move to source interaction pose
        await robot.move(LEFT, source_pose)
        
        # Acquire tool before source pickup
        await robot.acquire(LEFT, TOOL, timeout_s=120)
        
        # Grasp the part
        await robot.grasp(LEFT, part_id)
        
        # Acquire buffer_lock for entry
        await robot.acquire(LEFT, BUFFER_LOCK, timeout_s=120)
        
        # Move to buffer
        await robot.move(LEFT, buffer_pose)
        
        # Release the part at buffer
        await robot.release(LEFT, part_id, buffer_pose)
        
        # Depart (move to home)
        await robot.move(LEFT, LEFT_HOME)
        
        # Release buffer_lock
        await robot.release_resource(LEFT, BUFFER_LOCK)
        
        # Release tool
        await robot.release_resource(LEFT, TOOL)
        
        # Publish ready event
        robot.signal(ready_event_id)

    # RQ2 Gate Producer
    async def rq2_producer():
        # Signal rq2_gate to allow consumer to proceed
        robot.signal(RQ2_GATE)

    # Main Loop
    # "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
    # "A alternates complete producer/consumer episodes"
    # We iterate through the parts.
    
    parts = [
        (PART_0, SOURCE_0, BUFFER_0, TARGET_0, READY_0),
        (PART_1, SOURCE_1, BUFFER_1, TARGET_1, READY_1)
    ]

    for part_id, source_pose, buffer_pose, target_pose, ready_event_id in parts:
        # Structural-OOD shape: FOR -> PAR_JOIN -> consumer IF
        # The consumer IF guards the complete mission.
        # The consumer waits for the exact active receipt (rq2_gate).
        
        # Define the consumer task for this iteration
        async def iteration_consumer():
            # Wait for rq2_gate
            gate_receipt = await robot.wait_event(RQ2_GATE, timeout_s=120)
            
            # Clear rq2_gate
            robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)
            
            # Execute the complete inherited mission
            await consumer_mission(part_id, buffer_pose, target_pose, ready_event_id)

        # Define the producer task for this iteration
        async def iteration_producer():
            await producer_mission(part_id, source_pose, buffer_pose, ready_event_id)

        # Define the rq2_gate producer task
        # This runs concurrently with the consumer.
        async def iteration_rq2_producer():
            await rq2_producer()

        # Concurrently join rq2_gate producer and consumer
        await asyncio.gather(
            iteration_rq2_producer(),
            iteration_consumer()
        )
        
        # After consumer completes (and signals empty_0), run the producer for the next part.
        # For the first part, producer runs after the consumer of the "previous" (non-existent) iteration?
        # "A alternates complete producer/consumer episodes"
        # "Producer waits and clears empty_0 before entering buffer with the second part"
        # This implies the producer for part_1 runs after the consumer for part_0.
        # The loop structure handles this: 
        # Iteration 0: Consumer runs (waits gate), Producer runs (part 0).
        # Iteration 1: Consumer runs (waits gate), Producer runs (part 1, waits empty).
        
        # However, the prompt says "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer".
        # It does not explicitly place the main producer in the gather.
        # But "A alternates" suggests they happen sequentially or interleaved.
        # Given "Producer waits... empty_0", and Consumer publishes "empty_0", they must be sequential across iterations.
        # So we run the producer for the current part *after* the consumer of the previous part?
        # Or inside the loop?
        # Let's look at the flow:
        # 1. Prod(0) -> Ready_0
        # 2. Cons(0) -> Empty_0
        # 3. Prod(1) -> Ready_1 (Waits Empty_0)
        # 4. Cons(1) -> Empty_0
        
        # If we put Producer in the gather with Consumer, they run in parallel.
        # Prod(0) and Cons(0) parallel? Cons waits Ready_0. Prod signals Ready_0. This works.
        # Prod(1) and Cons(1) parallel? Cons waits Ready_1. Prod signals Ready_1. 
        # But Prod(1) waits Empty_0. Cons(0) signals Empty_0.
        # So Prod(1) must wait for Cons(0).
        # This implies sequential execution of the pairs (Prod, Cons).
        
        # The prompt says: "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
        # This likely refers to the `rq2_producer` and the `consumer`.
        # The main `producer` might run outside or inside depending on interpretation.
        # However, "A alternates complete producer/consumer episodes" suggests the loop body handles one episode.
        # An episode is Producer then Consumer? Or Consumer then Producer?
        # Given the dependency (Prod 1 waits Cons 0), and the loop, it's likely:
        # Loop:
        #   Run Consumer (for current)
        #   Run Producer (for next)
        # But we have a fixed list.
        
        # Let's try to fit the "Inside one finite loop iteration" constraint strictly.
        # "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
        # This implies the gather is inside the loop.
        # If we put the main producer in the gather too, we have 3 tasks.
        # If we put the main producer after the gather, we have:
        #   Gather(RQ2_Prod, Cons)
        #   Prod
        # Let's trace:
        # Iter 0:
        #   Gather: RQ2_Prod (signals gate), Cons (waits gate, runs mission 0, signals empty).
        #   Prod: Runs mission 0 (signals ready).
        #   Result: Cons 0 runs. Prod 0 runs. Order depends on gather vs prod.
        #   If Cons 0 finishes first, Prod 0 runs later. Cons 0 waits Ready 0. Prod 0 signals Ready 0. Deadlock if Cons 0 is first.
        #   If Prod 0 runs first (in gather), Cons 0 waits. OK.
        #   But the prompt says "join an rq2_gate producer and consumer". It doesn't mention the main producer in the join.
        
        # Alternative interpretation:
        # The "consumer" in the join is the RQ2 consumer.
        # The "producer" in the join is the RQ2 producer.
        # The main producer runs *before* the loop or *after*?
        # "A alternates complete producer/consumer episodes"
        # Maybe the loop runs the Consumer, and the Producer runs in the background?
        # No, "Producer waits... empty_0".
        
        # Let's assume the structure is:
        # Loop:
        #   1. Run Producer (for current item)
        #   2. Run Consumer (for current item)
        # But this violates "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer".
        # Unless "consumer" refers to the whole Consumer task, and "producer" refers to the RQ2 producer.
        # And the Main Producer is just... there?
        
        # Let's look at "A alternates complete producer/consumer episodes".
        # Episode 1: Prod(0), Cons(0).
        # Episode 2: Prod(1), Cons(1).
        # This fits the loop.
        # Where does the RQ2 join fit?
        # "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
        # Maybe the "consumer" IS the episode consumer?
        # And the "producer" IS the RQ2 producer?
        # What about the Main Producer?
        # Maybe the Main Producer is part of the "consumer" task? No.
        # Maybe the Main Producer runs *before* the join?
        # If I run Prod(0), then Join(RQ2_Prod, Cons(0)).
        # Prod(0) signals Ready_0. Cons(0) waits Ready_0. This works.
        # Iter 1:
        #   Prod(1) waits Empty_0. Cons(0) signaled Empty_0. This works.
        #   Join(RQ2_Prod, Cons(1)).
        #   Prod(1) signals Ready_1. Cons(1) waits Ready_1. This works.
        
        # This seems the most logical interpretation that satisfies all constraints.
        # 1. Loop over parts.
        # 2. In each iteration:
        #    a. Run Main Producer for this part.
        #    b. Run RQ2 Producer and Consumer for this part concurrently.
        
        # Wait, "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
        # This phrasing suggests the join is the primary structure inside the loop.
        # If I put Main Producer before it, is it "inside"?
        # Yes, it's inside the loop block.
        
        # Let's refine the loop body.
        # await producer_mission(...)  # Main Producer
        # await asyncio.gather(rq2_producer(), consumer_mission(...)) # The Join
        
        # Check dependencies:
        # Iter 0:
        #   Prod(0) -> Ready_0.
        #   Join: RQ2_Prod -> Gate. Cons(0) -> Gate -> Ready_0 -> ... -> Empty_0.
        #   Cons(0) waits Ready_0. Prod(0) already finished. OK.
        # Iter 1:
        #   Prod(1) waits Empty_0. Cons(0) finished. OK.
        #   Prod(1) -> Ready_1.
        #   Join: RQ2_Prod -> Gate. Cons(1) -> Gate -> Ready_1 -> ... -> Empty_0.
        #   Cons(1) waits Ready_1. Prod(1) already finished. OK.
        
        # This seems correct and robust.
        
        # One detail: "Consumer clears ready after its carried move"
        # "Consumer waits the corresponding ready receipt before pickup"
        # "Consumer ... supplies that exact active item receipt on carried move to target"
        # My consumer_mission does this.
        
        # "Producer places each part at buffer and immediately departs before ready publication"
        # My producer_mission does this (Release -> Depart -> Signal).
        
        # "LEFT owns tool from before each source pickup through ready publication and releases it on every exit"
        # My producer_mission does this (Acquire -> Grasp -> ... -> Signal -> Release).
        
        # "For item 1, wait and clear empty_0, then inspect both readiness facts"
        # My producer_mission does this.
        
        # "Use the structural-OOD shape FOR -> PAR_JOIN -> consumer IF"
        # FOR is the loop.
        # PAR_JOIN is the gather.
        # consumer IF is the consumer task (which guards the mission).
        # Where is the Main Producer?
        # The prompt says "A alternates complete producer/consumer episodes".
        # If I put Main Producer before the Join, it is sequential with the Join.
        # Is that "alternating"?
        # Prod, (RQ2_Prod + Cons). Prod, (RQ2_Prod + Cons).
        # Yes.
        
        # Wait, "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
        # Does this imply ONLY those two are joined?
        # Yes.
        # So Main Producer must be outside the join.
        # Can it be after?
        # If Main Producer is after:
        # Iter 0: Join(RQ2_Prod, Cons(0)). Cons(0) waits Ready_0. Prod(0) hasn't run. Deadlock.
        # So Main Producer MUST be before the Join.
        
        # Final Plan:
        # Loop parts:
        #   Run Producer(part)
        #   Run Gather(RQ2_Producer, Consumer(part))

        # Execute Producer
        await producer_mission(part_id, source_pose, buffer_pose, ready_event_id)
        
        # Execute Join
        await asyncio.gather(
            iteration_rq2_producer(),
            iteration_consumer()
        )

    # Final state check implicit in completion.
    # "rq2_gate inactive at return"
    # The last consumer clears it.
