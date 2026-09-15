import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # --- RQ2_GATE PROTOCOL ---
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order.
    # Complete all three rq2_gap resource checks before signalling rq2_gate.
    # Signal rq2_gate exactly once, wait its exact active receipt exactly once, and clear exactly that version.
    # Complete and clear the rq2_gate protocol before starting the complete inherited dual-arm mission.
    
    async def check_gap(gap_id: str):
        await robot.acquire("LEFT", gap_id, timeout_s=4.0)
        await robot.release_resource("LEFT", gap_id)

    await check_gap("rq2_gap_0")
    await check_gap("rq2_gap_1")
    await check_gap("rq2_gap_2")

    # Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # Wait immediately after the signal
    await robot.wait_event("rq2_gate", timeout_s=4.0)
    
    # Clear exactly that version
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- INHERITED DUAL-ARM MISSION ---
    # Variant B: A alternates complete producer/consumer episodes; 
    # B runs producer and consumer coroutines together.
    # Structure: CONCURRENT.
    
    # Resources
    buffer_lock = "buffer_lock"
    empty_event = "empty_0"
    ready_events = ["ready_0", "ready_1"]
    
    # Poses
    left_home = "left_home"
    left_wait = "left_wait"
    right_home = "right_home"
    right_wait = "right_wait"
    
    # Objects and locations
    items = ["part_0", "part_1"]
    sources = ["source_0", "source_1"]
    targets = ["target_0", "target_1"]
    buffer_poses = ["buffer_0", "buffer_1"]

    async def producer(item_idx: int):
        item_id = items[item_idx]
        source_pose = sources[item_idx]
        buffer_pose = buffer_poses[item_idx]
        ready_event = ready_events[item_idx]
        
        # 1. Wait and clear empty_0 before entering buffer with the second part.
        # (For the first part, empty_0 is already inactive/clearable, but we check/clear to be safe or if required)
        if item_idx == 1:
            await robot.wait_event(empty_event, timeout_s=4.0)
            # We need the version to clear. Since we just waited, we can clear the active one.
            # However, wait_event returns the receipt.
            empty_receipt = await robot.wait_event(empty_event, timeout_s=4.0)
            robot.clear_event(empty_event, expected_version=empty_receipt.version)
        
        # 2. Acquire buffer_lock for entry
        await robot.acquire("LEFT", buffer_lock, timeout_s=4.0)
        
        # 3. Move to source (Approach start)
        await robot.move("LEFT", left_home if item_idx == 0 else left_wait, timeout_s=4.0)
        
        # 4. Approach sequence: Move to interaction_pose (source)
        await robot.move("LEFT", source_pose, timeout_s=4.0)
        
        # 5. Grasp (Immediate required next call)
        await robot.grasp("LEFT", item_id)
        
        # 6. Move to buffer
        await robot.move("LEFT", buffer_pose, timeout_s=4.0)
        
        # 7. Release at buffer
        await robot.release("LEFT", item_id, buffer_pose)
        
        # 8. Depart immediately (Move away)
        await robot.move("LEFT", left_home if item_idx == 0 else left_wait, timeout_s=4.0)
        
        # 9. Release buffer_lock (Departure complete)
        await robot.release_resource("LEFT", buffer_lock)
        
        # 10. Publish ready event
        robot.signal(ready_event)

    async def consumer(item_idx: int):
        item_id = items[item_idx]
        buffer_pose = buffer_poses[item_idx]
        target_pose = targets[item_idx]
        ready_event = ready_events[item_idx]
        
        # 1. Wait the corresponding ready receipt
        ready_receipt = await robot.wait_event(ready_event, timeout_s=4.0)
        
        # 2. Acquire buffer_lock for entry
        await robot.acquire("RIGHT", buffer_lock, timeout_s=4.0)
        
        # 3. Move to wait/home (Approach start)
        await robot.move("RIGHT", right_home if item_idx == 0 else right_wait, timeout_s=4.0)
        
        # 4. Approach sequence: Move to interaction_pose (buffer)
        await robot.move("RIGHT", buffer_pose, timeout_s=4.0)
        
        # 5. Grasp (Immediate required next call)
        await robot.grasp("RIGHT", item_id)
        
        # 6. Depart immediately (Move away)
        await robot.move("RIGHT", right_home if item_idx == 0 else right_wait, timeout_s=4.0)
        
        # 7. Release buffer_lock (Departure complete)
        await robot.release_resource("RIGHT", buffer_lock)
        
        # 8. Supplies that exact active item receipt on carried move to target.
        await robot.move("RIGHT", target_pose, timeout_s=4.0, receipt=ready_receipt)
        
        # 9. Consumer clears ready after its carried move
        robot.clear_event(ready_event, expected_version=ready_receipt.version)
        
        # 10. Release on target
        await robot.release("RIGHT", item_id, target_pose)
        
        # 11. Depart before publishing empty_0
        await robot.move("RIGHT", right_home if item_idx == 0 else right_wait, timeout_s=4.0)
        
        # 12. Publish empty_0
        robot.signal(empty_event)

    # Run producer and consumer coroutines together (Variant B)
    # We run them concurrently for each item.
    # Since the buffer is capacity-one and lock is used, they will synchronize naturally.
    
    # Episode 0
    await asyncio.gather(
        producer(0),
        consumer(0)
    )
    
    # Episode 1
    await asyncio.gather(
        producer(1),
        consumer(1)
    )
