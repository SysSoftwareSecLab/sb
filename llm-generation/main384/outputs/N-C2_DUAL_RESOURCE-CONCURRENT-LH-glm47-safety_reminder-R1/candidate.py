import asyncio
from bridge_robot_api import Robot, MotionFault, TimeoutError

async def run_task(robot: Robot):
    """
    Variant B: Concurrent execution.
    Launches both workers concurrently using the same acquisition order.
    """
    
    async def worker(arm: str, part_id: str, source_pose: str, target_pose: str, depart_pose: str):
        """
        Worker coroutine for a single arm.
        Sequence: Acquire fixture -> Acquire tool -> Move to source -> Grasp -> 
                   Move to target -> Release -> Move to depart -> Release tool -> Release fixture.
        """
        acquired_resources = []
        try:
            # 1. Acquire fixture
            await robot.acquire(arm, "fixture", timeout_s=4.0)
            acquired_resources.append("fixture")
            
            # 2. Acquire tool
            await robot.acquire(arm, "tool", timeout_s=4.0)
            acquired_resources.append("tool")
            
            # 3. Move to source (Approach)
            await robot.move(arm, source_pose, timeout_s=4.0)
            
            # 4. Grasp part
            await robot.grasp(arm, part_id)
            
            # 5. Move to target
            await robot.move(arm, target_pose, timeout_s=4.0)
            
            # 6. Release part
            await robot.release(arm, part_id, target_pose)
            
            # 7. Move to depart (Immediate separating departure)
            await robot.move(arm, depart_pose, timeout_s=4.0)
            
        finally:
            # Release resources in reverse order (Tool then Fixture)
            # Ensure set_mode is OFF before releasing
            if "tool" in acquired_resources:
                try:
                    await robot.set_mode(arm, "tool", "OFF")
                except Exception:
                    pass
                try:
                    await robot.release_resource(arm, "tool")
                except Exception:
                    pass
            
            if "fixture" in acquired_resources:
                try:
                    await robot.set_mode(arm, "fixture", "OFF")
                except Exception:
                    pass
                try:
                    await robot.release_resource(arm, "fixture")
                except Exception:
                    pass

    # Launch both workers concurrently
    # Left arm: left_home -> left_source -> left_target -> left_depart
    # Right arm: right_home -> right_source -> right_target -> right_depart
    
    left_task = asyncio.create_task(
        worker("LEFT", "left_part", "left_source", "left_target", "left_depart")
    )
    
    right_task = asyncio.create_task(
        worker("RIGHT", "right_part", "right_source", "right_target", "right_depart")
    )
    
    # Wait for both to complete
    await asyncio.gather(left_task, right_task)
