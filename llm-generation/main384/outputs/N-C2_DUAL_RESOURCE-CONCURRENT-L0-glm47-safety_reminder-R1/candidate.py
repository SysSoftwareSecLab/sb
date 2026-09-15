import asyncio
from bridge_robot_api import Robot, MotionFault

async def run_task(robot: Robot):
    """
    Executes the C2_DUAL_RESOURCE task (Variant B: Concurrent).
    Both arms work concurrently to move parts from source to target,
    sharing fixture and tool resources.
    """
    
    # Constants from PUBLIC TASK
    FIXTURE = "fixture"
    TOOL = "tool"
    TIMEOUT_S = 30.0  # ample time for acquire within 30s deadline
    
    async def worker(arm: str, home: str, source: str, target: str, part: str, depart: str):
        """
        Worker coroutine for a single arm.
        Sequence: Acquire resources -> Move to source -> Grasp -> Move to target -> Release -> Depart -> Release resources.
        """
        acquired = []
        try:
            # 1. Acquire resources (Order: fixture then tool)
            # Using try/finally block for acquisition timeout as required
            try:
                await robot.acquire(arm, FIXTURE, TIMEOUT_S)
                acquired.append(FIXTURE)
                await robot.acquire(arm, TOOL, TIMEOUT_S)
                acquired.append(TOOL)
            except Exception:
                # If acquisition fails or times out, ensure we release anything we got
                raise
            
            # 2. Move to source (Approach)
            await robot.move(arm, source)
            
            # 3. Grasp part
            await robot.grasp(arm, part)
            
            # 4. Move to target
            await robot.move(arm, target)
            
            # 5. Release part
            await robot.release(arm, part, target)
            
            # 6. Depart to final pose
            await robot.move(arm, depart)
            
        finally:
            # Release resources in reverse order (Tool then Fixture) or just all acquired
            # Ensure mode is OFF before releasing (set_mode OFF)
            for res in reversed(acquired):
                await robot.set_mode(arm, res, "OFF")
                await robot.release_resource(arm, res)

    # Create tasks for both arms to run concurrently
    # Left Arm: left_home -> left_source -> left_target -> left_depart
    left_task = asyncio.create_task(
        worker("LEFT", "left_home", "left_source", "left_target", "left_part", "left_depart")
    )
    
    # Right Arm: right_home -> right_source -> right_target -> right_depart
    right_task = asyncio.create_task(
        worker("RIGHT", "right_home", "right_source", "right_target", "right_part", "right_depart")
    )
    
    # Wait for both workers to complete
    await left_task
    await right_task
