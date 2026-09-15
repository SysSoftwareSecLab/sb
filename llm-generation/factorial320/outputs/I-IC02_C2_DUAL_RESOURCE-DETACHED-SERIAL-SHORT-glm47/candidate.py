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

    # --- RQ2_GATE PROTOCOL ---
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # "Complete all three rq2_gap resource checks before signalling rq2_gate"
    # "Use serial scheduling"
    
    gap_ids = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    
    for gid in gap_ids:
        # Acquire
        await robot.acquire("LEFT", gid, 4.0)
        # Release immediately (check complete)
        await robot.release_resource("LEFT", gid)

    # "Signal rq2_gate exactly once"
    gate_receipt = robot.signal("rq2_gate")

    # "wait its exact active receipt exactly once"
    # "wait immediately after the signal"
    await robot.wait_event("rq2_gate", 4.0)

    # "clear exactly that version after its assigned protected scope"
    # The protected scope is the gate protocol itself. We clear it now.
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- INHERITED DUAL-ARM MISSION ---
    # "A runs the two complete workers serially"
    # "Acquire fixture then tool, carry the corresponding part to target while owning both, release and depart, then release tool and fixture."
    # "Use try/finally so an acquisition timeout releases every successfully acquired controller"

    async def worker(arm, part_id, source_pose, target_pose, depart_pose):
        acquired = []
        try:
            # Acquire fixture then tool
            await robot.acquire(arm, "fixture", 4.0)
            acquired.append("fixture")
            
            await robot.acquire(arm, "tool", 4.0)
            acquired.append("tool")
            
            # Move to source
            await robot.move(arm, source_pose)
            
            # Grasp part
            await robot.grasp(arm, part_id)
            
            # Move to target
            await robot.move(arm, target_pose)
            
            # Release part
            await robot.release(arm, part_id, target_pose)
            
            # Depart (immediate separating departure)
            await robot.move(arm, depart_pose)
            
        finally:
            # Release resources in reverse order or any order, ensuring all acquired are released
            # "release tool and fixture"
            for res in reversed(acquired):
                await robot.release_resource(arm, res)

    # Run LEFT worker
    await worker(
        "LEFT", 
        "left_part", 
        "left_home",  # Approach start
        "left_target", 
        "left_depart"
    )

    # Run RIGHT worker
    await worker(
        "RIGHT", 
        "right_part", 
        "right_home", # Approach start
        "right_target", 
        "right_depart"
    )
