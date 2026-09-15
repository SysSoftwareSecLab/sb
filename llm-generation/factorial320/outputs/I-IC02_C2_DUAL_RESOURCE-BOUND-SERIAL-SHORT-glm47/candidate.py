import asyncio
from bridge_robot_api import Robot, MotionFault, TimeoutError

async def run_task(robot: Robot):
    # Helper to manage resource acquisition with timeout and release on failure
    async def acquire_resource(arm, resource_id, timeout_s):
        try:
            await robot.acquire(arm, resource_id, timeout_s)
            return True
        except TimeoutError:
            return False

    # Helper to safely release a resource if owned
    async def safe_release_resource(arm, resource_id):
        try:
            await robot.release_resource(arm, resource_id)
        except Exception:
            pass

    # Helper to execute the dual-arm mission for a specific arm
    # This implements the "inherited dual-arm mission"
    async def run_dual_arm_worker(arm, part_id, home_pose, source_pose, target_pose, depart_pose):
        # Acquire fixture then tool
        await robot.acquire(arm, "fixture", 4.0)
        await robot.acquire(arm, "tool", 4.0)

        try:
            # Move to source
            await robot.move(arm, source_pose)
            # Grasp part
            await robot.grasp(arm, part_id)
            
            # Move to target
            await robot.move(arm, target_pose)
            # Release part
            await robot.release(arm, part_id, target_pose)
            
            # Depart
            await robot.move(arm, depart_pose)
        finally:
            # Release tool and fixture
            await robot.release_resource(arm, "tool")
            await robot.release_resource(arm, "fixture")

    # --- Main Execution Flow ---

    # 1. Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    # "never retain them at return" implies we release them immediately after acquisition/check
    # or ensure they are released by the end. The requirement "Acquire and release ... once each"
    # suggests a transactional check.
    
    gap_resources = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    
    for res in gap_resources:
        await robot.acquire("LEFT", res, 4.0)
        await robot.release_resource("LEFT", res)

    # 2. Signal rq2_gate exactly once
    gate_receipt = robot.signal("rq2_gate")

    # 3. Wait its exact active receipt exactly once
    # Note: The receipt we just signaled is the one we wait for.
    await robot.wait_event("rq2_gate", 4.0)

    # 4. Execute the complete inherited dual-arm mission
    # "Use serial scheduling for both the inherited dual-arm mission"
    # "A runs the two complete workers serially"
    
    # Worker for LEFT
    await run_dual_arm_worker(
        "LEFT", 
        "left_part", 
        "left_home", 
        "left_source", 
        "left_target", 
        "left_depart"
    )

    # Worker for RIGHT
    await run_dual_arm_worker(
        "RIGHT", 
        "right_part", 
        "right_home", 
        "right_source", 
        "right_target", 
        "right_depart"
    )

    # 5. Clear rq2_gate exactly that version after its assigned protected scope
    # The protected scope is the dual-arm mission.
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # 6. Ensure all resources are released and arms are at departures (handled by logic)
    # rq2_gap resources are already released.
    # Fixture and tool released in finally blocks.
    # Arms are at left_depart/right_depart.
