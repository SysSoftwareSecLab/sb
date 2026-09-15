import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    # --- RQ2 Gate Protocol ---
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order.
    # Complete all three rq2_gap resource checks before signalling rq2_gate.
    # Signal rq2_gate exactly once, wait its exact active receipt exactly once, 
    # and clear exactly that version after its assigned protected scope.
    # Complete and clear the rq2_gate protocol before starting the complete inherited dual-arm mission.
    
    gap_resources = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    for res_id in gap_resources:
        await robot.acquire("LEFT", res_id, timeout_s=4.0)
        await robot.release_resource("LEFT", res_id)
    
    gate_receipt = robot.signal("rq2_gate")
    # Wait immediately after the signal
    active_gate_receipt = await robot.wait_event("rq2_gate", timeout_s=4.0)
    # Clear exactly that version
    robot.clear_event("rq2_gate", expected_version=active_gate_receipt.version)

    # --- Inherited Dual-Arm Mission (Serial Schedule) ---
    # Variant A: Alternates complete producer/consumer episodes.
    # LEFT is Producer, RIGHT is Consumer.
    # Items: part_0, part_1.
    # Buffer: buffer_0 / buffer_1 (same physical location, item-specific contracts).
    # Lock: buffer_lock.
    
    # Helper for Producer Episode
    async def producer_episode(part_id: str, source_pose: str, buffer_pose: str, ready_event_id: str, empty_event_id: str):
        # 1. Wait and clear empty_0 before entering buffer with the second part.
        # (Only for part_1, as part_0 is the first part)
        if part_id == "part_1":
            empty_receipt = await robot.wait_event(empty_event_id, timeout_s=4.0)
            robot.clear_event(empty_event_id, expected_version=empty_receipt.version)
        
        # 2. Approach and Grasp
        # Approach sequence: start_pose -> interaction_pose (source)
        start_p = "left_home" if part_id == "part_0" else "left_wait"
        await robot.move("LEFT", start_p)
        await robot.move("LEFT", source_pose)
        obs = await robot.grasp("LEFT", part_id)
        
        # 3. Move to Buffer
        # Both participants own buffer_lock during buffer entry and departure.
        await robot.acquire("LEFT", "buffer_lock", timeout_s=4.0)
        await robot.move("LEFT", buffer_pose)
        
        # 4. Release at Buffer
        await robot.release("LEFT", part_id, buffer_pose)
        
        # 5. Depart immediately
        await robot.move("LEFT", start_p)
        await robot.release_resource("LEFT", "buffer_lock")
        
        # 6. Publish Ready
        robot.signal(ready_event_id)

    # Helper for Consumer Episode
    async def consumer_episode(part_id: str, buffer_pose: str, target_pose: str, ready_event_id: str, empty_event_id: str):
        # 1. Wait ready receipt
        ready_receipt = await robot.wait_event(ready_event_id, timeout_s=4.0)
        
        # 2. Approach and Grasp
        # Approach sequence: start_pose -> interaction_pose (buffer)
        start_p = "right_home" if part_id == "part_0" else "right_wait"
        await robot.move("RIGHT", start_p)
        await robot.move("RIGHT", buffer_pose)
        obs = await robot.grasp("RIGHT", part_id)
        
        # 3. Move to Target with Receipt
        # Consumer supplies that exact active item receipt on carried move to target.
        await robot.acquire("RIGHT", "buffer_lock", timeout_s=4.0)
        await robot.move("RIGHT", target_pose, receipt=ready_receipt)
        
        # 4. Clear Ready after carried move
        robot.clear_event(ready_event_id, expected_version=ready_receipt.version)
        
        # 5. Release at Target
        await robot.release("RIGHT", part_id, target_pose)
        
        # 6. Depart immediately
        await robot.move("RIGHT", start_p)
        await robot.release_resource("RIGHT", "buffer_lock")
        
        # 7. Publish Empty
        robot.signal(empty_event_id)

    # --- Execution: Part 0 ---
    # Producer places part_0 at buffer and immediately departs before ready publication.
    await producer_episode("part_0", "source_0", "buffer_0", "ready_0", "empty_0")
    
    # Consumer waits ready_0 receipt before pickup...
    await consumer_episode("part_0", "buffer_0", "target_0", "ready_0", "empty_0")

    # --- Execution: Part 1 ---
    # Producer waits empty_0 before entering buffer with second part.
    await producer_episode("part_1", "source_1", "buffer_1", "ready_1", "empty_0")
    
    # Consumer waits ready_1 receipt...
    await consumer_episode("part_1", "buffer_1", "target_1", "ready_1", "empty_0")

    # --- Final State ---
    # Return arms to home
    await robot.move("LEFT", "left_home")
    await robot.move("RIGHT", "right_home")
