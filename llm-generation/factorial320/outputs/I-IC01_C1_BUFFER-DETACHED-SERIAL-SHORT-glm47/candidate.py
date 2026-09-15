import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- RQ2_GATE PROTOCOL ---
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order.
    # Complete all three rq2_gap resource checks before signalling rq2_gate.
    # Signal rq2_gate exactly once, wait its exact active receipt exactly once, 
    # and clear exactly that version after its assigned protected scope.
    # Complete and clear the rq2_gate protocol before starting the complete inherited dual-arm mission.
    
    # Acquire gaps
    await robot.acquire("LEFT", "rq2_gap_0", 4.0)
    await robot.release_resource("LEFT", "rq2_gap_0")
    
    await robot.acquire("LEFT", "rq2_gap_1", 4.0)
    await robot.release_resource("LEFT", "rq2_gap_1")
    
    await robot.acquire("LEFT", "rq2_gap_2", 4.0)
    await robot.release_resource("LEFT", "rq2_gap_2")
    
    # Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # Wait immediately after the signal
    await robot.wait_event("rq2_gate", 4.0)
    
    # Clear exactly that version after its assigned protected scope
    # (Scope is the protocol itself, which is effectively done now)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- INHERITED DUAL-ARM MISSION ---
    # Variant A: Serial scheduling.
    # Part 0: LEFT (Producer) -> RIGHT (Consumer)
    # Part 1: LEFT (Producer) -> RIGHT (Consumer)
    
    # --- PART 0 ---
    
    # 1. Producer (LEFT) places part_0 at buffer and immediately departs before ready publication.
    # Approach source_0
    await robot.move("LEFT", "source_0")
    # Grasp part_0
    grasp_obs_0 = await robot.grasp("LEFT", "part_0")
    # Move to buffer_0
    await robot.move("LEFT", "buffer_0")
    # Release part_0 at buffer_0
    await robot.release("LEFT", "part_0", "buffer_0")
    # Depart immediately (move to left_wait)
    await robot.move("LEFT", "left_wait")
    
    # Publish ready_0
    ready_0_receipt = robot.signal("ready_0")
    
    # 2. Consumer (RIGHT) waits the corresponding ready receipt before pickup.
    await robot.wait_event("ready_0", 4.0)
    
    # 3. Consumer supplies that exact active item receipt on carried move to target.
    # Approach buffer_0
    await robot.move("RIGHT", "buffer_0")
    # Grasp part_0
    await robot.grasp("RIGHT", "part_0")
    # Move to target_0 with receipt
    await robot.move("RIGHT", "target_0", receipt=ready_0_receipt)
    
    # 4. Consumer clears ready after its carried move, releases on target and departs before publishing empty_0.
    robot.clear_event("ready_0", expected_version=ready_0_receipt.version)
    await robot.release("RIGHT", "part_0", "target_0")
    # Depart immediately (move to right_wait)
    await robot.move("RIGHT", "right_wait")
    
    # Publish empty_0
    empty_0_receipt = robot.signal("empty_0")
    
    # --- PART 1 ---
    
    # 5. Producer (LEFT) waits and clears empty_0 before entering buffer with the second part.
    await robot.wait_event("empty_0", 4.0)
    robot.clear_event("empty_0", expected_version=empty_0_receipt.version)
    
    # Producer (LEFT) places part_1 at buffer and immediately departs before ready publication.
    # Approach source_1
    await robot.move("LEFT", "source_1")
    # Grasp part_1
    grasp_obs_1 = await robot.grasp("LEFT", "part_1")
    # Move to buffer_1
    await robot.move("LEFT", "buffer_1")
    # Release part_1 at buffer_1
    await robot.release("LEFT", "part_1", "buffer_1")
    # Depart immediately (move to left_home)
    await robot.move("LEFT", "left_home")
    
    # Publish ready_1
    ready_1_receipt = robot.signal("ready_1")
    
    # Consumer (RIGHT) waits the corresponding ready receipt before pickup.
    await robot.wait_event("ready_1", 4.0)
    
    # Consumer supplies that exact active item receipt on carried move to target.
    # Approach buffer_1
    await robot.move("RIGHT", "buffer_1")
    # Grasp part_1
    await robot.grasp("RIGHT", "part_1")
    # Move to target_1 with receipt
    await robot.move("RIGHT", "target_1", receipt=ready_1_receipt)
    
    # Consumer clears ready after its carried move, releases on target and departs before publishing empty_0.
    robot.clear_event("ready_1", expected_version=ready_1_receipt.version)
    await robot.release("RIGHT", "part_1", "target_1")
    # Depart immediately (move to right_home)
    await robot.move("RIGHT", "right_home")
    
    # Note: empty_0 is not signaled again as per "empty arms at homes; buffer empty; lock free; events inactive" goal.
    # The cycle ends with both parts at targets and arms at homes.
