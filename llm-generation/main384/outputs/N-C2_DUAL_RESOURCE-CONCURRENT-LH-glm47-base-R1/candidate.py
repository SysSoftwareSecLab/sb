import asyncio
from bridge_robot_api import Robot, MotionFault, TimeoutError

async def run_task(robot: Robot):
    """
    Variant B: Concurrent execution of dual-arm workers.
    Both arms acquire fixture then tool, move parts, release, depart, and release resources.
    """
    
    async def worker(arm: str, source_pose: str, target_pose: str, depart_pose: str, part_id: str):
        """
        Worker coroutine for a single arm.
        Sequence: Acquire -> Grasp -> Move -> Release -> Depart -> Release Resources.
        """
        acquired_resources = []
        try:
            # 1. Acquire fixture
            await robot.acquire(arm, "fixture", 120.0)
            acquired_resources.append("fixture")
            
            # 2. Acquire tool
            await robot.acquire(arm, "tool", 120.0)
            acquired_resources.append("tool")
            
            # 3. Approach and Grasp
            # Approach is implicit in move to source_pose
            await robot.move(arm, source_pose)
            await robot.grasp(arm, part_id)
            
            # 4. Move to target
            await robot.move(arm, target_pose)
            
            # 5. Release part
            await robot.release(arm, part_id, target_pose)
            
            # 6. Depart (immediate separating departure)
            await robot.move(arm, depart_pose)
            
        except (MotionFault, TimeoutError):
            # On failure, attempt to release any acquired resources
            # Note: safe_stop is not used as per constraints for normal path
            raise
        finally:
            # Release resources in reverse order (tool then fixture)
            # Ensure mode is OFF before releasing
            for res_id in reversed(acquired_resources):
                try:
                    await robot.set_mode(arm, res_id, "OFF")
                    await robot.release_resource(arm, res_id)
                except Exception:
                    # Ignore errors during cleanup to ensure best effort
                    pass

    # Define parameters for LEFT and RIGHT arms based on PUBLIC TASK
    # LEFT: left_home -> left_source -> left_target -> left_depart
    # RIGHT: right_home -> right_source -> right_target -> right_depart
    
    left_task = worker(
        arm="LEFT",
        source_pose="left_source",
        target_pose="left_target",
        depart_pose="left_depart",
        part_id="left_part"
    )
    
    right_task = worker(
        arm="RIGHT",
        source_pose="right_source",
        target_pose="right_target",
        depart_pose="right_depart",
        part_id="right_part"
    )
    
    # Run workers concurrently (Variant B)
    await asyncio.gather(left_task, right_task)
