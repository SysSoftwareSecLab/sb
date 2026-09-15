import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- RQ2_GATE Protocol ---
    # Signal rq2_gate exactly once
    gate_receipt = robot.signal("rq2_gate")
    
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    for res_id in ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]:
        await robot.acquire("LEFT", res_id, 4.0)
        await robot.release_resource("LEFT", res_id)
    
    # Wait for rq2_gate exactly once, using the exact active receipt
    await robot.wait_event("rq2_gate", 4.0)
    
    # Clear rq2_gate exactly that version
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- Inherited Dual-Arm Mission (Serial Schedule) ---
    # Items and poses
    items = ["part_0", "part_1"]
    sources = ["source_0", "source_1"]
    targets = ["target_0", "target_1"]
    ready_events = ["ready_0", "ready_1"]
    
    # Initial positions
    # LEFT at left_home, RIGHT at right_home
    
    for i in range(2):
        item = items[i]
        source = sources[i]
        target = targets[i]
        ready_evt = ready_events[i]
        buffer_pose = f"buffer_{i}"
        
        # --- Producer (LEFT) ---
        # 1. Acquire tool
        await robot.acquire("LEFT", "tool", 4.0)
        
        # 2. Move to source (Approach)
        # part_0: left_home -> source_0
        # part_1: left_home -> left_wait -> source_1
        if i == 0:
            await robot.move("LEFT", source)
        else:
            await robot.move("LEFT", "left_wait")
            await robot.move("LEFT", source)
            
        # 3. Grasp part
        await robot.grasp("LEFT", item)
        
        # 4. Move to buffer
        # part_0: source_0 -> buffer_0
        # part_1: source_1 -> buffer_1
        await robot.move("LEFT", buffer_pose)
        
        # 5. Acquire buffer_lock
        await robot.acquire("LEFT", "buffer_lock", 4.0)
        
        # 6. Release part at buffer
        await robot.release("LEFT", item, buffer_pose)
        
        # 7. Depart buffer (Immediate separating departure)
        # part_0: buffer_0 -> left_home
        # part_1: buffer_1 -> left_home
        await robot.move("LEFT", "left_home")
        
        # 8. Release buffer_lock
        await robot.release_resource("LEFT", "buffer_lock")
        
        # 9. Release tool
        await robot.release_resource("LEFT", "tool")
        
        # 10. Signal ready event
        ready_receipt = robot.signal(ready_evt)
        
        # --- Consumer (RIGHT) ---
        # 1. Wait for ready receipt
        await robot.wait_event(ready_evt, 4.0)
        
        # 2. Move to buffer (Approach)
        # part_0: right_home -> buffer_0
        # part_1: right_home -> right_wait -> buffer_1
        if i == 0:
            await robot.move("RIGHT", buffer_pose)
        else:
            await robot.move("RIGHT", "right_wait")
            await robot.move("RIGHT", buffer_pose)
            
        # 3. Grasp part
        await robot.grasp("RIGHT", item)
        
        # 4. Acquire buffer_lock
        await robot.acquire("RIGHT", "buffer_lock", 4.0)
        
        # 5. Depart buffer (Immediate separating departure)
        # part_0: buffer_0 -> right_home
        # part_1: buffer_1 -> right_home
        await robot.move("RIGHT", "right_home")
        
        # 6. Release buffer_lock
        await robot.release_resource("RIGHT", "buffer_lock")
        
        # 7. Move to target with receipt
        # part_0: right_home -> target_0
        # part_1: right_home -> target_1
        await robot.move("RIGHT", target, receipt=ready_receipt)
        
        # 8. Clear ready event
        robot.clear_event(ready_evt, expected_version=ready_receipt.version)
        
        # 9. Release part at target
        await robot.release("RIGHT", item, target)
        
        # 10. Depart target
        # part_0: target_0 -> right_home
        # part_1: target_1 -> right_home
        await robot.move("RIGHT", "right_home")
        
        # --- Inter-episode Synchronization ---
        if i == 0:
            # Producer waits and clears empty_0 before entering buffer with second part
            await robot.wait_event("empty_0", 4.0)
            robot.clear_event("empty_0", expected_version=1)
            
            # For item 1, inspect both readiness facts
            # C8 joins the two checks inside the loop branch
            # Note: inspect returns Observation, we don't need the value, just the action
            await robot.inspect("LEFT", "line_clear")
            await robot.inspect("LEFT", "receiver_ready")
            
        else:
            # Consumer publishes empty_0 after releasing part_1 and departing
            robot.signal("empty_0")
