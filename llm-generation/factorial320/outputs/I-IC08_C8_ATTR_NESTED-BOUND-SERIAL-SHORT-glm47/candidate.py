import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
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
    
    # Items
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    # Resources
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    GAP_0 = "rq2_gap_0"
    GAP_1 = "rq2_gap_1"
    GAP_2 = "rq2_gap_2"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    GATE = "rq2_gate"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"
    
    # Timeouts
    TIMEOUT_S = 4.0
    
    # --- RQ2 Gap Resource Checks (LEFT) ---
    # Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order
    await robot.acquire(LEFT, GAP_0, TIMEOUT_S)
    await robot.release_resource(LEFT, GAP_0)
    
    await robot.acquire(LEFT, GAP_1, TIMEOUT_S)
    await robot.release_resource(LEFT, GAP_1)
    
    await robot.acquire(LEFT, GAP_2, TIMEOUT_S)
    await robot.release_resource(LEFT, GAP_2)
    
    # --- Signal RQ2 Gate ---
    # Signal rq2_gate exactly once
    gate_receipt = robot.signal(GATE)
    
    # Wait its exact active receipt exactly once
    # "wait immediately after the signal"
    active_gate_receipt = await robot.wait_event(GATE, TIMEOUT_S)
    
    # --- Inherited Dual-Arm Mission (Serial) ---
    # "Use serial scheduling for both the inherited dual-arm mission"
    # "Keep rq2_gate active while executing the complete inherited dual-arm mission"
    
    # === Episode 1: part_0 ===
    
    # 1. Producer (LEFT) picks up part_0 from source_0
    # Acquire tool
    await robot.acquire(LEFT, TOOL, TIMEOUT_S)
    
    # Move to source_0 (Approach start)
    await robot.move(LEFT, SOURCE_0, TIMEOUT_S)
    
    # Grasp part_0
    grasp_obs_0 = await robot.grasp(LEFT, PART_0)
    
    # 2. Producer moves to buffer_0
    # Acquire buffer_lock
    await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
    
    # Move to buffer_0
    await robot.move(LEFT, BUFFER_0, TIMEOUT_S)
    
    # 3. Producer releases part_0 at buffer_0
    await robot.release(LEFT, PART_0, BUFFER_0)
    
    # 4. Producer departs buffer immediately
    await robot.move(LEFT, LEFT_HOME, TIMEOUT_S)
    
    # Release buffer_lock
    await robot.release_resource(LEFT, BUFFER_LOCK)
    
    # 5. Producer signals ready_0
    ready_0_receipt = robot.signal(READY_0)
    
    # Release tool
    await robot.release_resource(LEFT, TOOL)
    
    # 6. Consumer (RIGHT) waits for ready_0
    active_ready_0 = await robot.wait_event(READY_0, TIMEOUT_S)
    
    # 7. Consumer picks up part_0 from buffer_0
    # Move to buffer_0 (Approach start)
    await robot.move(RIGHT, BUFFER_0, TIMEOUT_S)
    
    # Grasp part_0
    await robot.grasp(RIGHT, PART_0)
    
    # 8. Consumer moves to target_0 with receipt
    # "supplies that exact active item receipt on carried move to target"
    await robot.move(RIGHT, TARGET_0, TIMEOUT_S, receipt=active_ready_0)
    
    # 9. Consumer clears ready_0
    # "Consumer clears ready after its carried move"
    robot.clear_event(READY_0, expected_version=active_ready_0.version)
    
    # 10. Consumer releases part_0 at target_0
    await robot.release(RIGHT, PART_0, TARGET_0)
    
    # 11. Consumer departs target immediately
    await robot.move(RIGHT, RIGHT_HOME, TIMEOUT_S)
    
    # 12. Consumer signals empty_0
    robot.signal(EMPTY_0)
    
    # === Episode 2: part_1 ===
    
    # 1. Producer (LEFT) waits and clears empty_0
    # "Producer waits and clears empty_0 before entering buffer with the second part"
    active_empty_0 = await robot.wait_event(EMPTY_0, TIMEOUT_S)
    robot.clear_event(EMPTY_0, expected_version=active_empty_0.version)
    
    # 2. Producer inspects both readiness facts
    # "For item 1, wait and clear empty_0, then inspect both readiness facts"
    # "C8 joins the two checks inside the loop branch" -> Serial execution of inspections
    await robot.inspect(LEFT, FACT_LINE_CLEAR)
    await robot.inspect(LEFT, FACT_RECEIVER_READY)
    
    # 3. Producer picks up part_1 from source_1
    # Acquire tool
    await robot.acquire(LEFT, TOOL, TIMEOUT_S)
    
    # Move to source_1 (Approach start)
    await robot.move(LEFT, SOURCE_1, TIMEOUT_S)
    
    # Grasp part_1
    grasp_obs_1 = await robot.grasp(LEFT, PART_1)
    
    # 4. Producer moves to buffer_1
    # Acquire buffer_lock
    await robot.acquire(LEFT, BUFFER_LOCK, TIMEOUT_S)
    
    # Move to buffer_1
    await robot.move(LEFT, BUFFER_1, TIMEOUT_S)
    
    # 5. Producer releases part_1 at buffer_1
    await robot.release(LEFT, PART_1, BUFFER_1)
    
    # 6. Producer departs buffer immediately
    await robot.move(LEFT, LEFT_HOME, TIMEOUT_S)
    
    # Release buffer_lock
    await robot.release_resource(LEFT, BUFFER_LOCK)
    
    # 7. Producer signals ready_1
    ready_1_receipt = robot.signal(READY_1)
    
    # Release tool
    await robot.release_resource(LEFT, TOOL)
    
    # 8. Consumer (RIGHT) waits for ready_1
    active_ready_1 = await robot.wait_event(READY_1, TIMEOUT_S)
    
    # 9. Consumer picks up part_1 from buffer_1
    # Move to buffer_1 (Approach start)
    await robot.move(RIGHT, BUFFER_1, TIMEOUT_S)
    
    # Grasp part_1
    await robot.grasp(RIGHT, PART_1)
    
    # 10. Consumer moves to target_1 with receipt
    await robot.move(RIGHT, TARGET_1, TIMEOUT_S, receipt=active_ready_1)
    
    # 11. Consumer clears ready_1
    robot.clear_event(READY_1, expected_version=active_ready_1.version)
    
    # 12. Consumer releases part_1 at target_1
    await robot.release(RIGHT, PART_1, TARGET_1)
    
    # 13. Consumer departs target immediately
    await robot.move(RIGHT, RIGHT_HOME, TIMEOUT_S)
    
    # --- Clear RQ2 Gate ---
    # "clear only after the mission"
    robot.clear_event(GATE, expected_version=active_gate_receipt.version)
