import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- Phase 1: RQ2 Gate Protocol (Serial) ---
    # 1. Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # 2. Acquire and release rq2_gap resources in numeric order with LEFT
    #    Task requires serial scheduling.
    for res_id in ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]:
        # Acquire
        await robot.acquire("LEFT", res_id, timeout_s=4.0)
        # Release (must be OFF, which is initial mode)
        await robot.release_resource("LEFT", res_id)
    
    # 3. Wait for rq2_gate (exact active receipt)
    #    Task requires waiting AFTER resource checks.
    await robot.wait_event("rq2_gate", timeout_s=4.0)
    
    # 4. Clear rq2_gate
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- Phase 2: Inherited Dual-Arm Mission (Serial) ---
    # Task: "A runs candidate LEFT then RIGHT serially"
    # Task: "Both workers independently inspect allocation once before choosing their own branch."
    
    # 1. LEFT Inspect
    obs_left = await robot.inspect("LEFT", "allocation")
    
    # 2. RIGHT Inspect
    obs_right = await robot.inspect("RIGHT", "allocation")
    
    # Determine selected arm from LEFT's observation
    # Value structure: {"item_id": "shared_part", "selected_arm": "LEFT"}
    selected_arm = obs_left.value["selected_arm"]
    
    # 3. Execute Transport Logic based on selection
    # Task: "Only the arm named by the current controller-issued allocation may propose..."
    # Task: "The unselected arm makes no move/grasp/release call."
    
    if selected_arm == "LEFT":
        # LEFT performs the transport
        # Move to source (Approach)
        await robot.move("LEFT", "shared_source", timeout_s=4.0)
        
        # Grasp with observation
        await robot.grasp("LEFT", "shared_part", observation=obs_left)
        
        # Move to target (Transport)
        await robot.move("LEFT", "shared_target", timeout_s=4.0)
        
        # Release
        await robot.release("LEFT", "shared_part", "shared_target")
        
        # Depart immediately
        await robot.move("LEFT", "left_depart", timeout_s=4.0)
        
        # RIGHT does nothing (stays at right_home)
        
    elif selected_arm == "RIGHT":
        # RIGHT performs the transport
        # Move to source (Approach)
        await robot.move("RIGHT", "shared_source", timeout_s=4.0)
        
        # Grasp with observation
        await robot.grasp("RIGHT", "shared_part", observation=obs_right)
        
        # Move to target (Transport)
        await robot.move("RIGHT", "shared_target", timeout_s=4.0)
        
        # Release
        await robot.release("RIGHT", "shared_part", "shared_target")
        
        # Depart immediately
        await robot.move("RIGHT", "right_depart", timeout_s=4.0)
        
        # LEFT does nothing (stays at left_home)
