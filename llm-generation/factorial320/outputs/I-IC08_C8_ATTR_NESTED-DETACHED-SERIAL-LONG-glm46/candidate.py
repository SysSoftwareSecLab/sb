import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- RQ2_GATE PROTOCOL ---
    # 1. Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # 2. Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    for res_id in ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]:
        await robot.acquire("LEFT", res_id, 120.0)
        await robot.release_resource("LEFT", res_id)
    
    # 3. Wait for rq2_gate (exact active receipt)
    await robot.wait_event("rq2_gate", 120.0)
    
    # 4. Clear rq2_gate (exact version)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- INHERITED DUAL-ARM MISSION ---
    # Helper to execute the producer-consumer episode for a single part
    async def episode(part_id: str, source_pose: str, buffer_pose: str, target_pose: str, ready_event_id: str, start_pose: str):
        # --- PRODUCER (LEFT) ---
        # 1. Acquire tool
        await robot.acquire("LEFT", "tool", 120.0)
        
        # 2. Approach and Grasp
        await robot.move("LEFT", start_pose)
        await robot.move("LEFT", source_pose)
        obs = await robot.grasp("LEFT", part_id)
        
        # 3. Transport to buffer
        await robot.acquire("LEFT", "buffer_lock", 120.0)
        await robot.move("LEFT", buffer_pose)
        await robot.release("LEFT", part_id, buffer_pose)
        
        # 4. Depart buffer and release lock
        await robot.move("LEFT", start_pose)
        await robot.release_resource("LEFT", "buffer_lock")
        
        # 5. Publish ready
        ready_receipt = robot.signal(ready_event_id)
        
        # 6. Release tool
        await robot.release_resource("LEFT", "tool")

        # --- CONSUMER (RIGHT) ---
        # 1. Wait for ready
        await robot.wait_event(ready_event_id, 120.0)
        
        # 2. Approach and Grasp
        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", buffer_pose)
        await robot.grasp("RIGHT", part_id)
        
        # 3. Acquire lock for departure
        await robot.acquire("RIGHT", "buffer_lock", 120.0)
        
        # 4. Move to target with receipt
        await robot.move("RIGHT", target_pose, receipt=ready_receipt)
        
        # 5. Clear ready
        robot.clear_event(ready_event_id, expected_version=ready_receipt.version)
        
        # 6. Release and depart
        await robot.release("RIGHT", part_id, target_pose)
        await robot.move("RIGHT", "right_home")
        await robot.release_resource("RIGHT", "buffer_lock")

    # --- EXECUTION ---
    
    # Episode 0: part_0
    await episode(
        part_id="part_0",
        source_pose="source_0",
        buffer_pose="buffer_0",
        target_pose="target_0",
        ready_event_id="ready_0",
        start_pose="left_home"
    )
    
    # Episode 1: part_1
    # 1. Wait and clear empty_0
    await robot.wait_event("empty_0", 120.0)
    empty_receipt = robot.signal("empty_0") # Get current version to clear
    robot.clear_event("empty_0", expected_version=empty_receipt.version)
    
    # 2. Inspect both readiness facts (C8 joins checks inside loop branch)
    # Note: C7 checks serially, C8 joins. We perform them sequentially here.
    await robot.inspect("LEFT", "line_clear")
    await robot.inspect("LEFT", "receiver_ready")
    
    # 3. Run episode
    await episode(
        part_id="part_1",
        source_pose="source_1",
        buffer_pose="buffer_1",
        target_pose="target_1",
        ready_event_id="ready_1",
        start_pose="left_wait"
    )
