import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- RQ2 Gate Protocol ---
    # 1. Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # 2. Acquire and release rq2_gap resources in numeric order with LEFT
    #    "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    #    "never retain them at return"
    #    "complete all three rq2_gap resource checks, and only then wait for rq2_gate"
    
    # Gap 0
    await robot.acquire("LEFT", "rq2_gap_0", timeout_s=4.0)
    await robot.release_resource("LEFT", "rq2_gap_0")
    
    # Gap 1
    await robot.acquire("LEFT", "rq2_gap_1", timeout_s=4.0)
    await robot.release_resource("LEFT", "rq2_gap_1")
    
    # Gap 2
    await robot.acquire("LEFT", "rq2_gap_2", timeout_s=4.0)
    await robot.release_resource("LEFT", "rq2_gap_2")
    
    # 3. Wait for rq2_gate
    #    "wait its exact active receipt exactly once"
    await robot.wait_event("rq2_gate", timeout_s=4.0)
    
    # 4. Clear rq2_gate
    #    "clear exactly that version after its assigned protected scope"
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- Inherited Dual-Arm Mission (Serial Schedule) ---
    #    "A alternates complete producer/consumer episodes"
    #    "LEFT owns tool from before each source pickup through ready publication"
    
    # --- Episode 1: part_0 ---
    
    # Producer (LEFT)
    # 1. Acquire tool
    await robot.acquire("LEFT", "tool", timeout_s=4.0)
    
    # 2. Move to source_0 (Approach start_pose is left_home)
    await robot.move("LEFT", "source_0")
    
    # 3. Grasp part_0
    await robot.grasp("LEFT", "part_0")
    
    # 4. Move to buffer_0
    await robot.move("LEFT", "buffer_0")
    
    # 5. Acquire buffer_lock
    await robot.acquire("LEFT", "buffer_lock", timeout_s=4.0)
    
    # 6. Release part_0 at buffer_0
    await robot.release("LEFT", "part_0", "buffer_0")
    
    # 7. Depart buffer (immediate separating departure)
    await robot.move("LEFT", "left_home")
    
    # 8. Release buffer_lock
    await robot.release_resource("LEFT", "buffer_lock")
    
    # 9. Signal ready_0
    ready_0_receipt = robot.signal("ready_0")
    
    # 10. Release tool
    await robot.release_resource("LEFT", "tool")
    
    # Consumer (RIGHT)
    # 1. Wait ready_0
    await robot.wait_event("ready_0", timeout_s=4.0)
    
    # 2. Move to buffer_0 (Approach start_pose is right_home)
    await robot.move("RIGHT", "buffer_0")
    
    # 3. Grasp part_0
    await robot.grasp("RIGHT", "part_0")
    
    # 4. Move to target_0 with receipt
    await robot.move("RIGHT", "target_0", receipt=ready_0_receipt)
    
    # 5. Clear ready_0
    robot.clear_event("ready_0", expected_version=ready_0_receipt.version)
    
    # 6. Release part_0 at target_0
    await robot.release("RIGHT", "part_0", "target_0")
    
    # 7. Depart target
    await robot.move("RIGHT", "right_home")
    
    # 8. Signal empty_0
    robot.signal("empty_0")

    # --- Episode 2: part_1 ---
    
    # Producer (LEFT)
    # 1. Wait and clear empty_0
    empty_0_receipt = await robot.wait_event("empty_0", timeout_s=4.0)
    robot.clear_event("empty_0", expected_version=empty_0_receipt.version)
    
    # 2. Inspect both readiness facts (C7 checks serially)
    #    "For item 1, wait and clear empty_0, then inspect both readiness facts"
    #    Facts: line_clear, receiver_ready
    await robot.inspect("LEFT", "line_clear")
    await robot.inspect("LEFT", "receiver_ready")
    
    # 3. Acquire tool
    await robot.acquire("LEFT", "tool", timeout_s=4.0)
    
    # 4. Move to source_1 (Approach start_pose is left_wait)
    await robot.move("LEFT", "source_1")
    
    # 5. Grasp part_1
    await robot.grasp("LEFT", "part_1")
    
    # 6. Move to buffer_1
    await robot.move("LEFT", "buffer_1")
    
    # 7. Acquire buffer_lock
    await robot.acquire("LEFT", "buffer_lock", timeout_s=4.0)
    
    # 8. Release part_1 at buffer_1
    await robot.release("LEFT", "part_1", "buffer_1")
    
    # 9. Depart buffer
    await robot.move("LEFT", "left_home")
    
    # 10. Release buffer_lock
    await robot.release_resource("LEFT", "buffer_lock")
    
    # 11. Signal ready_1
    ready_1_receipt = robot.signal("ready_1")
    
    # 12. Release tool
    await robot.release_resource("LEFT", "tool")
    
    # Consumer (RIGHT)
    # 1. Wait ready_1
    await robot.wait_event("ready_1", timeout_s=4.0)
    
    # 2. Move to buffer_1 (Approach start_pose is right_wait)
    await robot.move("RIGHT", "buffer_1")
    
    # 3. Grasp part_1
    await robot.grasp("RIGHT", "part_1")
    
    # 4. Move to target_1 with receipt
    await robot.move("RIGHT", "target_1", receipt=ready_1_receipt)
    
    # 5. Clear ready_1
    robot.clear_event("ready_1", expected_version=ready_1_receipt.version)
    
    # 6. Release part_1 at target_1
    await robot.release("RIGHT", "part_1", "target_1")
    
    # 7. Depart target
    await robot.move("RIGHT", "right_home")
    
    # 8. Signal empty_0 (Final state requires empty_0 active? No, "events inactive" in goal, but "Consumer clears ready... before publishing empty_0")
    #    Goal: "events inactive". So we should clear empty_0 if we signal it?
    #    "Consumer clears ready after its carried move, releases on target and departs before publishing empty_0."
    #    This implies we signal it. But goal says events inactive.
    #    However, "empty_0" is a program_clearable event. We can clear it.
    #    Let's signal it to satisfy the "publishing" step, then clear it to satisfy "events inactive".
    empty_final_receipt = robot.signal("empty_0")
    robot.clear_event("empty_0", expected_version=empty_final_receipt.version)
