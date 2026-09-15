import asyncio
from bridge_robot_api import Robot, MotionFault

async def run_task(robot: Robot):
    """
    Implementation for task C2_DUAL_RESOURCE-SERIAL-L0 (Variant A).
    Executes two workers serially.
    Each worker acquires resources (fixture, tool), moves a part to target,
    releases the part, departs, and releases resources.
    """
    
    # Configuration constants derived from PUBLIC TASK
    RESOURCES = ["fixture", "tool"]
    TIMEOUT_S = 4.0  # default_move_timeout_s
    
    # Define the worker coroutine for a single arm
    async def worker(arm: str, part_id: str, start_pose: str, target_pose: str, depart_pose: str):
        acquired = []
        try:
            # 1. Acquire resources in order: fixture then tool
            for res_id in RESOURCES:
                await robot.acquire(arm, res_id, TIMEOUT_S)
                acquired.append(res_id)
            
            # 2. Move to source (Approach)
            await robot.move(arm, start_pose, timeout_s=TIMEOUT_S)
            
            # 3. Grasp the part
            await robot.grasp(arm, part_id)
            
            # 4. Move to target
            await robot.move(arm, target_pose, timeout_s=TIMEOUT_S)
            
            # 5. Release the part
            await robot.release(arm, part_id, target_pose)
            
            # 6. Depart (Move to depart pose)
            await robot.move(arm, depart_pose, timeout_s=TIMEOUT_S)
            
        except Exception:
            # Allow exceptions to propagate or handle as needed, 
            # but finally block ensures resource cleanup.
            raise
        finally:
            # 7. Release resources in reverse order (tool then fixture)
            # Ensure mode is OFF before releasing (initial mode is OFF, no set_mode needed)
            for res_id in reversed(acquired):
                await robot.release_resource(arm, res_id)

    # Variant A: Run the two complete workers serially.
    # Left worker
    await worker(
        arm="LEFT",
        part_id="left_part",
        start_pose="left_home",
        target_pose="left_target",
        depart_pose="left_depart"
    )
    
    # Right worker
    await worker(
        arm="RIGHT",
        part_id="right_part",
        start_pose="right_home",
        target_pose="right_target",
        depart_pose="right_depart"
    )
