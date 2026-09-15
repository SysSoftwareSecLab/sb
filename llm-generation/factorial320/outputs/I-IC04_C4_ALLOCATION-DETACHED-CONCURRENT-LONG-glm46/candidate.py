import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_DEPART = "left_depart"
    POSE_RIGHT_HOME = "right_home"
    POSE_SHARED_SOURCE = "shared_source"
    POSE_SHARED_TARGET = "shared_target"
    
    OBJ_SHARED_PART = "shared_part"
    FACT_ALLOCATION = "allocation"
    
    EVT_GATE = "rq2_gate"
    RES_GAP_0 = "rq2_gap_0"
    RES_GAP_1 = "rq2_gap_1"
    RES_GAP_2 = "rq2_gap_2"
    
    TIMEOUT_S = 4.0
    ACQUIRE_TIMEOUT = 1.0
    
    # --- Phase 1: RQ2 Gate Protocol ---
    # "Signal rq2_gate exactly once, wait its exact active receipt exactly once, and clear exactly that version"
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    
    # 1. Signal the gate
    gate_receipt = robot.signal(EVT_GATE)
    
    # 2. Acquire and release resources in numeric order with LEFT arm
    # "never retain them at return"
    for res_id in [RES_GAP_0, RES_GAP_1, RES_GAP_2]:
        await robot.acquire(ARM_LEFT, res_id, ACQUIRE_TIMEOUT)
        await robot.release_resource(ARM_LEFT, res_id)
        
    # 3. Wait for the gate (only after resource checks)
    await robot.wait_event(EVT_GATE, TIMEOUT_S)
    
    # 4. Clear the gate (exact version)
    robot.clear_event(EVT_GATE, expected_version=gate_receipt.version)
    
    # --- Phase 2: Inherited Dual-Arm Mission ---
    # "Both workers independently inspect allocation once before choosing their own branch."
    # "A runs candidate LEFT then RIGHT serially; B gathers them concurrently."
    # "Use joined concurrent scheduling for both the inherited dual-arm mission"
    
    async def worker(arm: str):
        # 1. Inspect allocation
        obs_alloc = await robot.inspect(arm, FACT_ALLOCATION)
        
        # 2. Determine if this arm is selected
        # allocation value: {"item_id": "shared_part", "selected_arm": "LEFT"}
        selected_arm = obs_alloc.value["selected_arm"]
        is_selected = (selected_arm == arm)
        
        if is_selected:
            # Selected Arm Path
            # "Only the arm named by the current controller-issued allocation may propose shared_source approach..."
            # "The selected grasp must carry that arm's own current allocation observation"
            
            # Approach
            start_pose = POSE_LEFT_HOME if arm == ARM_LEFT else POSE_RIGHT_HOME
            await robot.move(arm, start_pose, timeout_s=TIMEOUT_S)
            await robot.move(arm, POSE_SHARED_SOURCE, timeout_s=TIMEOUT_S)
            
            # Grasp with observation
            await robot.grasp(arm, OBJ_SHARED_PART, observation=obs_alloc)
            
            # Transport
            await robot.move(arm, POSE_SHARED_TARGET, timeout_s=TIMEOUT_S)
            
            # Release
            await robot.release(arm, OBJ_SHARED_PART, POSE_SHARED_TARGET)
            
            # Depart immediately
            depart_pose = POSE_LEFT_DEPART if arm == ARM_LEFT else POSE_RIGHT_HOME
            await robot.move(arm, depart_pose, timeout_s=TIMEOUT_S)
        else:
            # Unselected Arm Path
            # "The unselected arm makes no move/grasp/release call."
            # "nonselected RIGHT empty at right_home" (or LEFT at left_depart)
            # Since we start at home and do nothing, we are already at the goal state.
            pass

    # Run workers concurrently
    await asyncio.gather(
        worker(ARM_LEFT),
        worker(ARM_RIGHT)
    )
