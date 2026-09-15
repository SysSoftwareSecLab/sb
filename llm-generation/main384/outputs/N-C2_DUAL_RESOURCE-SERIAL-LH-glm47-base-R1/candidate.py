import asyncio
from bridge_robot_api import Robot, MotionFault, TimeoutError

async def run_task(robot: Robot):
    """
    Variant A: Serial execution of two workers.
    Each worker acquires resources, moves part, releases part, departs, and releases resources.
    """
    
    # Configuration from PUBLIC TASK
    RESOURCES = ["fixture", "tool"]
    TIMEOUT_S = 4.0  # default_move_timeout_s
    
    # Define the worker coroutine for a single arm
    async def worker(arm: str, part_id: str, start_pose: str, target_pose: str, depart_pose: str):
        acquired = []
        try:
            # 1. Acquire resources in order
            for res in RESOURCES:
                await robot.acquire(arm, res, TIMEOUT_S)
                acquired.append(res)
            
            # 2. Approach (move to source)
            await robot.move(arm, start_pose, timeout_s=TIMEOUT_S)
            
            # 3. Grasp part
            await robot.grasp(arm, part_id)
            
            # 4. Transport (move to target)
            await robot.move(arm, target_pose, timeout_s=TIMEOUT_S)
            
            # 5. Release part
            await robot.release(arm, part_id, target_pose)
            
            # 6. Depart (move to depart pose)
            await robot.move(arm, depart_pose, timeout_s=TIMEOUT_S)
            
        finally:
            # 7. Release resources in reverse order
            # Ensure mode is OFF before releasing (set_mode OFF)
            for res in reversed(acquired):
                await robot.set_mode(arm, res, "OFF")
                await robot.release_resource(arm, res)

    # Variant A: Run workers serially
    # Worker 1: LEFT
    await worker(
        arm="LEFT",
        part_id="left_part",
        start_pose="left_home",
        target_pose="left_target",
        depart_pose="left_depart"
    )
    
    # Worker 2: RIGHT
    await worker(
        arm="RIGHT",
        part_id="right_part",
        start_pose="right_home",
        target_pose="right_target",
        depart_pose="right_depart"
    )
