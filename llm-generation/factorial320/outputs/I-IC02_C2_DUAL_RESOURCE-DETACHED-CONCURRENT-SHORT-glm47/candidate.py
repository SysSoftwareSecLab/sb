import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot) -> None:
    # Helper to manage resource acquisition with timeout and release on failure
    async def acquire_resource(arm: str, resource_id: str, timeout_s: float):
        try:
            await robot.acquire(arm, resource_id, timeout_s)
        except TimeoutError:
            raise
        except Exception:
            # If acquire fails for other reasons, we still treat it as not owned
            raise

    # RQ2 Gap Check Protocol
    # Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order
    async def run_rq2_gap_checks():
        gap_ids = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
        for gid in gap_ids:
            await robot.acquire("LEFT", gid, 4.0)
            await robot.release_resource("LEFT", gid)

    # RQ2 Gate Protocol
    # Complete gap checks, signal gate, wait gate, clear gate
    async def run_rq2_gate_protocol():
        await run_rq2_gap_checks()
        
        # Signal rq2_gate exactly once
        receipt = robot.signal("rq2_gate")
        
        # Wait its exact active receipt exactly once
        # Using a short timeout as per wait_event constraints
        await robot.wait_event("rq2_gate", 4.0)
        
        # Clear exactly that version after its assigned protected scope
        robot.clear_event("rq2_gate", expected_version=receipt.version)

    # Inherited Dual-Arm Mission
    # Acquire fixture then tool, carry part to target, release, depart, release resources
    async def run_dual_arm_worker(arm: str, home_pose: str, source_pose: str, target_pose: str, depart_pose: str, part_id: str):
        # Acquire fixture then tool
        await robot.acquire(arm, "fixture", 4.0)
        await robot.acquire(arm, "tool", 4.0)
        
        try:
            # Move to source (approach start)
            await robot.move(arm, home_pose)
            
            # Approach sequence: start_pose -> interaction_pose
            # Must be followed immediately by grasp
            await robot.move(arm, source_pose)
            await robot.grasp(arm, part_id)
            
            # Move to target
            await robot.move(arm, target_pose)
            
            # Release part
            await robot.release(arm, part_id, target_pose)
            
            # Depart immediately
            await robot.move(arm, depart_pose)
            
        finally:
            # Release tool and fixture in finally block
            # Ensure mode is OFF before release (initial mode is OFF, no set_mode needed)
            await robot.release_resource(arm, "tool")
            await robot.release_resource(arm, "fixture")

    # Main Execution Flow
    # 1. Complete and clear the rq2_gate protocol before starting the complete inherited dual-arm mission.
    await run_rq2_gate_protocol()
    
    # 2. Launch both workers concurrently using the same acquisition order (fixture then tool)
    # Use joined concurrent scheduling
    left_task = asyncio.create_task(
        run_dual_arm_worker(
            "LEFT", 
            "left_home", 
            "left_source", 
            "left_target", 
            "left_depart", 
            "left_part"
        )
    )
    
    right_task = asyncio.create_task(
        run_dual_arm_worker(
            "RIGHT", 
            "right_home", 
            "right_source", 
            "right_target", 
            "right_depart", 
            "right_part"
        )
    )
    
    # Wait for both tasks to complete
    await asyncio.gather(left_task, right_task)
