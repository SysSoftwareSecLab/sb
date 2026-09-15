import asyncio
from bridge_robot_api import Robot, MotionFault, ContractError

async def run_task(robot: Robot):
    # Helper to manage resource acquisition with timeout and release on failure
    async def acquire_safe(arm, resource_id, timeout_s):
        try:
            await robot.acquire(arm, resource_id, timeout_s)
            return True
        except TimeoutError:
            return False

    # Helper to manage resource release with mode OFF
    async def release_safe(arm, resource_id):
        try:
            await robot.set_mode(arm, resource_id, "OFF")
            await robot.release_resource(arm, resource_id)
        except Exception:
            pass # Ignore errors during cleanup

    # --- Phase 1: RQ2 Gap Checks (LEFT arm) ---
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    gap_resources = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    for res in gap_resources:
        acquired = await acquire_safe("LEFT", res, 4.0)
        if acquired:
            await release_safe("LEFT", res)
        else:
            # If acquisition fails, we cannot proceed as per "Complete all three ... before signalling"
            return

    # --- Phase 2: Signal and Wait for rq2_gate ---
    # Signal rq2_gate exactly once
    gate_receipt = robot.signal("rq2_gate")
    
    # Wait its exact active receipt exactly once
    try:
        await robot.wait_event("rq2_gate", 4.0)
    except TimeoutError:
        return

    # --- Phase 3: Inherited Dual-Arm Mission (Serial) ---
    # "A runs the two complete workers serially."
    # Worker 1: LEFT arm (fixture -> tool -> left_part -> left_target -> left_depart)
    # Worker 2: RIGHT arm (fixture -> tool -> right_part -> right_target -> right_depart)
    
    # Note: Resources must be released after each worker as per "release tool and fixture" 
    # implied per worker context in serial execution to allow the next worker to acquire them.
    
    async def run_left_worker():
        owned = []
        try:
            # Acquire fixture then tool
            if not await acquire_safe("LEFT", "fixture", 4.0): return
            owned.append("fixture")
            if not await acquire_safe("LEFT", "tool", 4.0): return
            owned.append("tool")
            
            # Move to source, grasp, move to target, release
            await robot.move("LEFT", "left_home")
            await robot.move("LEFT", "left_source")
            await robot.grasp("LEFT", "left_part")
            await robot.move("LEFT", "left_target")
            await robot.release("LEFT", "left_part", "left_target")
            
            # Depart
            await robot.move("LEFT", "left_depart")
        finally:
            # Release tool and fixture in reverse order or any order
            for res in reversed(owned):
                await release_safe("LEFT", res)

    async def run_right_worker():
        owned = []
        try:
            # Acquire fixture then tool
            if not await acquire_safe("RIGHT", "fixture", 4.0): return
            owned.append("fixture")
            if not await acquire_safe("RIGHT", "tool", 4.0): return
            owned.append("tool")
            
            # Move to source, grasp, move to target, release
            await robot.move("RIGHT", "right_home")
            await robot.move("RIGHT", "right_source")
            await robot.grasp("RIGHT", "right_part")
            await robot.move("RIGHT", "right_target")
            await robot.release("RIGHT", "right_part", "right_target")
            
            # Depart
            await robot.move("RIGHT", "right_depart")
        finally:
            for res in reversed(owned):
                await release_safe("RIGHT", res)

    # Execute serially
    await run_left_worker()
    await run_right_worker()

    # --- Phase 4: Clear rq2_gate ---
    # Clear exactly that version after its assigned protected scope (after mission)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
