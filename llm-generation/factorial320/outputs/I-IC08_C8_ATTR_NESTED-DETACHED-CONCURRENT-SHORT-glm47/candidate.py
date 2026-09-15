import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- RQ2 Gate Protocol ---
    # Acquire resources in numeric order with LEFT
    await robot.acquire("LEFT", "rq2_gap_0", 4.0)
    await robot.acquire("LEFT", "rq2_gap_1", 4.0)
    await robot.acquire("LEFT", "rq2_gap_2", 4.0)
    
    # Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # Wait immediately after signal
    await robot.wait_event("rq2_gate", 4.0)
    
    # Clear rq2_gate
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
    
    # Release resources
    await robot.release_resource("LEFT", "rq2_gap_0")
    await robot.release_resource("LEFT", "rq2_gap_1")
    await robot.release_resource("LEFT", "rq2_gap_2")

    # --- Inherited Dual-Arm Mission ---
    
    # Helper for Producer (LEFT)
    async def producer(item_id: str, source_pose: str, ready_event_id: str, wait_empty: bool = False):
        # Wait for empty_0 if required (for item 1)
        if wait_empty:
            await robot.wait_event("empty_0", 4.0)
            # Clear empty_0
            # Note: empty_0 initial version is 0. Assuming it is signaled once before.
            # We need the receipt of the signal to clear it. 
            # Since we don't have the receipt passed in, we assume the version is 1 (signaled once).
            # Or we rely on the fact that wait_event returns the receipt.
            empty_receipt = await robot.wait_event("empty_0", 4.0)
            robot.clear_event("empty_0", expected_version=empty_receipt.version)

        # Acquire tool
        await robot.acquire("LEFT", "tool", 4.0)
        
        # Acquire buffer_lock
        await robot.acquire("LEFT", "buffer_lock", 4.0)
        
        # Move to source
        await robot.move("LEFT", source_pose)
        
        # Grasp
        await robot.grasp("LEFT", item_id)
        
        # Move to buffer
        # buffer_0 and buffer_1 are identical coordinates. Using buffer_0 for both.
        await robot.move("LEFT", "buffer_0")
        
        # Release
        await robot.release("LEFT", item_id, "buffer_0")
        
        # Depart buffer (move to left_home)
        await robot.move("LEFT", "left_home")
        
        # Release buffer_lock
        await robot.release_resource("LEFT", "buffer_lock")
        
        # Signal ready
        ready_receipt = robot.signal(ready_event_id)
        
        # Release tool
        await robot.release_resource("LEFT", "tool")
        
        return ready_receipt

    # Helper for Consumer (RIGHT)
    async def consumer(item_id: str, target_pose: str, ready_event_id: str):
        # Wait for ready
        ready_receipt = await robot.wait_event(ready_event_id, 4.0)
        
        # Acquire buffer_lock
        await robot.acquire("RIGHT", "buffer_lock", 4.0)
        
        # Move to buffer
        await robot.move("RIGHT", "buffer_0")
        
        # Grasp
        await robot.grasp("RIGHT", item_id)
        
        # Depart buffer (move to right_home)
        await robot.move("RIGHT", "right_home")
        
        # Release buffer_lock
        await robot.release_resource("RIGHT", "buffer_lock")
        
        # Move to target with receipt
        await robot.move("RIGHT", target_pose, receipt=ready_receipt)
        
        # Clear ready event
        robot.clear_event(ready_event_id, expected_version=ready_receipt.version)
        
        # Release
        await robot.release("RIGHT", item_id, target_pose)
        
        # Depart target (move to right_home)
        await robot.move("RIGHT", "right_home")
        
        # Signal empty_0
        robot.signal("empty_0")

    # --- Execution ---
    
    # Item 0: Producer runs, Consumer waits
    # Producer for part_0: source_0, ready_0, no wait_empty
    prod_0 = asyncio.create_task(producer("part_0", "source_0", "ready_0"))
    
    # Consumer for part_0: target_0, ready_0
    cons_0 = asyncio.create_task(consumer("part_0", "target_0", "ready_0"))
    
    await prod_0
    await cons_0
    
    # Item 1: Producer waits empty, Consumer waits ready
    # Producer for part_1: source_1, ready_1, wait_empty=True
    # Also inspect facts before proceeding?
    # "For item 1, wait and clear empty_0, then inspect both readiness facts"
    # The inspection happens inside the producer flow after clearing empty_0.
    # We need to modify producer for item 1 or handle it here.
    # Let's create a specific task for item 1 producer that includes inspection.
    
    async def producer_item_1():
        # Wait and clear empty_0
        empty_receipt = await robot.wait_event("empty_0", 4.0)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)
        
        # Inspect both readiness facts
        # "C8 joins the two checks inside the loop branch"
        # We inspect receiver_ready and line_clear
        obs1 = await robot.inspect("LEFT", "receiver_ready")
        obs2 = await robot.inspect("LEFT", "line_clear")
        
        # Proceed with production
        await robot.acquire("LEFT", "tool", 4.0)
        await robot.acquire("LEFT", "buffer_lock", 4.0)
        await robot.move("LEFT", "source_1")
        await robot.grasp("LEFT", "part_1")
        await robot.move("LEFT", "buffer_0")
        await robot.release("LEFT", "part_1", "buffer_0")
        await robot.move("LEFT", "left_home")
        await robot.release_resource("LEFT", "buffer_lock")
        ready_receipt = robot.signal("ready_1")
        await robot.release_resource("LEFT", "tool")
        return ready_receipt

    prod_1 = asyncio.create_task(producer_item_1())
    cons_1 = asyncio.create_task(consumer("part_1", "target_1", "ready_1"))
    
    await prod_1
    await cons_1
