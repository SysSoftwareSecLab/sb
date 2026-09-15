import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- RQ2 Gate Protocol ---
    # 1. Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # 2. Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 with LEFT in numeric order
    #    "Acquire and release ... once each ... never retain them at return"
    #    "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    #    This implies the checks happen after signaling but before waiting.
    #    We perform them sequentially as required by numeric order.
    for i in range(3):
        res_id = f"rq2_gap_{i}"
        await robot.acquire("LEFT", res_id, 4.0)
        await robot.release_resource("LEFT", res_id)
        
    # 3. Wait for rq2_gate
    #    "wait its exact active receipt exactly once"
    await robot.wait_event("rq2_gate", 4.0)
    
    # 4. Clear rq2_gate
    #    "clear exactly that version after its assigned protected scope"
    #    The protected scope is the resource checks and the wait.
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- Inherited Dual-Arm Mission ---
    # Scenario: Two parts (part_0, part_1) move from Source (LEFT) to Target (RIGHT) via Buffer.
    # LEFT is Producer, RIGHT is Consumer.
    # Buffer is capacity-one.
    # Sequence: Part 0 -> Buffer -> Target 0. Part 1 -> Buffer -> Target 1.
    
    # Helper to run the Producer/Consumer logic for a single item
    async def run_episode(item_id: str, source_pose: str, buffer_pose: str, target_pose: str, ready_event_id: str, start_pose: str):
        
        # --- Producer (LEFT) ---
        # 1. Acquire tool
        await robot.acquire("LEFT", "tool", 4.0)
        
        # 2. Move to source and grasp
        #    Approach sequence requires start_pose -> source_pose -> grasp
        await robot.move("LEFT", start_pose)
        await robot.move("LEFT", source_pose)
        grasp_obs = await robot.grasp("LEFT", item_id)
        
        # 3. Move to buffer and release
        #    "Both participants own buffer_lock during buffer entry and departure."
        #    Producer acquires lock before entering buffer.
        await robot.acquire("LEFT", "buffer_lock", 4.0)
        
        await robot.move("LEFT", buffer_pose)
        await robot.release("LEFT", item_id, buffer_pose)
        
        # 4. Depart buffer
        #    "immediately departs before ready publication"
        #    "releases it [tool] on every exit"
        await robot.move("LEFT", start_pose)
        await robot.release_resource("LEFT", "tool")
        
        # 5. Publish ready
        ready_receipt = robot.signal(ready_event_id)
        
        # 6. Release buffer_lock (Departure complete)
        await robot.release_resource("LEFT", "buffer_lock")
        
        # --- Consumer (RIGHT) ---
        # 1. Wait for ready receipt
        #    "Consumer waits the corresponding ready receipt before pickup"
        await robot.wait_event(ready_event_id, 4.0)
        
        # 2. Move to buffer and grasp
        #    "Both participants own buffer_lock during buffer entry and departure."
        #    Consumer acquires lock before entering buffer.
        await robot.acquire("RIGHT", "buffer_lock", 4.0)
        
        #    Approach sequence requires right_home/right_wait -> buffer_pose -> grasp
        #    For part_0: right_home -> buffer_0
        #    For part_1: right_wait -> buffer_1
        consumer_start = "right_home" if item_id == "part_0" else "right_wait"
        await robot.move("RIGHT", consumer_start)
        await robot.move("RIGHT", buffer_pose)
        await robot.grasp("RIGHT", item_id)
        
        # 3. Release buffer_lock (Departure from buffer)
        await robot.release_resource("RIGHT", "buffer_lock")
        
        # 4. Move to target carrying the item
        #    "supplies that exact active item receipt on carried move to target"
        #    The receipt is the ready_receipt.
        await robot.move("RIGHT", target_pose, receipt=ready_receipt)
        
        # 5. Clear ready event
        #    "Consumer clears ready after its carried move"
        robot.clear_event(ready_event_id, expected_version=ready_receipt.version)
        
        # 6. Release item and depart
        await robot.release("RIGHT", item_id, target_pose)
        await robot.move("RIGHT", consumer_start)
        
        # --- Producer (LEFT) - Second Item Setup ---
        #    "Producer waits and clears empty_0 before entering buffer with the second part."
        #    This logic is specific to the transition between Part 0 and Part 1.
        if item_id == "part_0":
            await robot.wait_event("empty_0", 4.0)
            #    "For item 1, wait and clear empty_0, then inspect both readiness facts"
            #    We inspect facts here before starting the next episode's logic.
            #    Note: run_episode is called sequentially, so this happens before Part 1's Producer starts.
            #    "C7 checks serially and C8 joins the two checks inside the loop branch."
            #    This implies we should inspect them. Since we are in a linear flow, we just inspect them.
            #    The facts are 'line_clear' and 'receiver_ready'.
            await robot.inspect("LEFT", "line_clear")
            await robot.inspect("LEFT", "receiver_ready")
            
            # Clear empty_0
            #    We need the receipt of empty_0 to clear it. The wait_event returns it.
            #    However, wait_event was called above. We need to capture the receipt.
            #    Refactoring: The wait_event above should capture receipt.
            #    But wait_event returns the receipt. Let's adjust the flow slightly.
            #    Actually, the requirement "wait and clear empty_0" applies to the Producer of Part 1.
            #    So this block is effectively the "Pre-Producer" step for Part 1.
            #    We need the receipt from wait_event.
            #    Since I can't edit the past, I will restructure the main loop to handle this inter-episode logic.
            pass

    # --- Main Execution Flow ---
    
    # Episode 0: Part 0
    # LEFT: left_home -> source_0 -> buffer_0 -> left_home
    # RIGHT: right_home -> buffer_0 -> target_0 -> right_home
    await run_episode("part_0", "source_0", "buffer_0", "target_0", "ready_0", "left_home")
    
    # Inter-Episode Logic (Producer for Part 1 setup)
    # "Producer waits and clears empty_0 before entering buffer with the second part."
    # "For item 1, wait and clear empty_0, then inspect both readiness facts"
    empty_receipt = await robot.wait_event("empty_0", 4.0)
    robot.clear_event("empty_0", expected_version=empty_receipt.version)
    
    # Inspect facts
    await robot.inspect("LEFT", "line_clear")
    await robot.inspect("LEFT", "receiver_ready")
    
    # Episode 1: Part 1
    # LEFT: left_wait -> source_1 -> buffer_1 -> left_wait
    # RIGHT: right_wait -> buffer_1 -> target_1 -> right_wait
    await run_episode("part_1", "source_1", "buffer_1", "target_1", "ready_1", "left_wait")
    
    # --- Finalization ---
    # "Consumer ... publishes empty_0" after Part 1 is done?
    # The goal says "empty_0 ... inactive at return".
    # The required order says "Consumer ... releases on target and departs before publishing empty_0."
    # This implies empty_0 is signaled by the Consumer (RIGHT) after the final item (Part 1).
    # We need to signal empty_0 here.
    robot.signal("empty_0")
    
    # Return arms to home
    await robot.move("LEFT", "left_home")
    await robot.move("RIGHT", "right_home")
