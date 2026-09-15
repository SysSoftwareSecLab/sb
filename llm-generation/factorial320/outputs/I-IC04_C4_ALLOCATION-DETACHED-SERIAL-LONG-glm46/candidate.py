import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    SHARED_PART = "shared_part"
    ALLOCATION_FACT = "allocation"
    EVENT_ID = "rq2_gate"
    RESOURCES = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_DEPART = "left_depart"
    RIGHT_HOME = "right_home"
    RIGHT_DEPART = "right_depart"
    SHARED_SOURCE = "shared_source"
    SHARED_TARGET = "shared_target"

    # Timeout
    TIMEOUT = 4.0

    # --- Phase 1: RQ2 Gate Protocol (Serial) ---
    
    # 1. Inspect allocation (Both workers inspect once)
    # Variant A runs LEFT then RIGHT serially.
    obs_left_alloc = await robot.inspect(LEFT, ALLOCATION_FACT)
    obs_right_alloc = await robot.inspect(RIGHT, ALLOCATION_FACT)

    # 2. Signal rq2_gate exactly once
    gate_receipt = robot.signal(EVENT_ID)

    # 3. Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    for res_id in RESOURCES:
        await robot.acquire(LEFT, res_id, TIMEOUT)
        await robot.release_resource(LEFT, res_id)

    # 4. Wait for rq2_gate (exact active receipt)
    # The spec says "wait its exact active receipt exactly once". 
    # Since we just signaled it, we wait for it to become active (it is active immediately upon signal).
    # We must wait for the specific version we signaled.
    # wait_event returns the active receipt.
    active_gate_receipt = await robot.wait_event(EVENT_ID, TIMEOUT)
    
    # 5. Clear rq2_gate (exact version)
    robot.clear_event(EVENT_ID, expected_version=active_gate_receipt.version)

    # --- Phase 2: Inherited Dual-Arm Mission (Serial) ---

    # Determine selected arm from LEFT's observation
    # obs_left_alloc.value is {"item_id": "shared_part", "selected_arm": "LEFT"}
    selected_arm = obs_left_alloc.value["selected_arm"]
    
    # The unselected arm makes no move/grasp/release call.
    # It must end at its home pose (already there).
    
    if selected_arm == LEFT:
        # Sequence for LEFT
        # 1. Approach shared_source
        await robot.move(LEFT, SHARED_SOURCE, timeout_s=TIMEOUT)
        
        # 2. Grasp shared_part with observation
        # "The selected grasp must carry that arm's own current allocation observation"
        await robot.grasp(LEFT, SHARED_PART, observation=obs_left_alloc)
        
        # 3. Transport to shared_target
        await robot.move(LEFT, SHARED_TARGET, timeout_s=TIMEOUT)
        
        # 4. Release at target
        await robot.release(LEFT, SHARED_PART, SHARED_TARGET)
        
        # 5. Immediately depart
        await robot.move(LEFT, LEFT_DEPART, timeout_s=TIMEOUT)
        
        # RIGHT stays at RIGHT_HOME (no moves)
        
    else:
        # Sequence for RIGHT
        # 1. Approach shared_source
        await robot.move(RIGHT, SHARED_SOURCE, timeout_s=TIMEOUT)
        
        # 2. Grasp shared_part with observation
        # Note: RIGHT uses its own observation (obs_right_alloc) which matches the fact.
        await robot.grasp(RIGHT, SHARED_PART, observation=obs_right_alloc)
        
        # 3. Transport to shared_target
        await robot.move(RIGHT, SHARED_TARGET, timeout_s=TIMEOUT)
        
        # 4. Release at target
        await robot.release(RIGHT, SHARED_PART, SHARED_TARGET)
        
        # 5. Immediately depart
        await robot.move(RIGHT, RIGHT_DEPART, timeout_s=TIMEOUT)
        
        # LEFT stays at LEFT_HOME (no moves)

    # End state:
    # shared_part at shared_target
    # Selected arm empty at depart
    # Non-selected arm empty at home
    # rq2_gate inactive (cleared)
    # Resources free and OFF (released)
