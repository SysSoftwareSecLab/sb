import asyncio
from bridge_robot_api import Robot, MotionFault, TimeoutError

async def run_task(robot: Robot):
    # Constants from task spec
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    RES_FIXTURE = "fixture"
    RES_TOOL = "tool"
    
    # Poses
    POSE_L_HOME = "left_home"
    POSE_R_HOME = "right_home"
    POSE_L_SOURCE = "left_source"
    POSE_R_SOURCE = "right_source"
    POSE_L_TARGET = "left_target"
    POSE_R_TARGET = "right_target"
    POSE_L_DEPART = "left_depart"
    POSE_R_DEPART = "right_depart"
    
    # Objects
    OBJ_L_PART = "left_part"
    OBJ_R_PART = "right_part"
    
    # Durations
    DUR_MOVE = 1.0
    TIMEOUT_ACQUIRE = 4.0
    
    async def worker(arm: str, home_pose: str, source_pose: str, target_pose: str, depart_pose: str, part_id: str):
        # Local tracking for try/finally cleanup
        owned_resources = []
        
        try:
            # 1. Acquire resources (Fixture then Tool)
            # Acquire Fixture
            try:
                await robot.acquire(arm, RES_FIXTURE, TIMEOUT_ACQUIRE)
                owned_resources.append(RES_FIXTURE)
            except TimeoutError:
                raise
            
            # Acquire Tool
            try:
                await robot.acquire(arm, RES_TOOL, TIMEOUT_ACQUIRE)
                owned_resources.append(RES_TOOL)
            except TimeoutError:
                raise
            
            # 2. Move to Source
            await robot.move(arm, source_pose)
            
            # 3. Grasp Part
            # Approach is implicit in move to source_pose as per approach_sequences
            await robot.grasp(arm, part_id)
            
            # 4. Move to Target
            await robot.move(arm, target_pose)
            
            # 5. Release Part
            await robot.release(arm, part_id, target_pose)
            
            # 6. Depart immediately
            await robot.move(arm, depart_pose)
            
        finally:
            # Release resources in reverse order (Tool then Fixture)
            # Ensure mode is OFF before releasing
            if RES_TOOL in owned_resources:
                try:
                    await robot.set_mode(arm, RES_TOOL, "OFF")
                    await robot.release_resource(arm, RES_TOOL)
                except Exception:
                    pass # Ignore cleanup errors to ensure other resources are attempted
            
            if RES_FIXTURE in owned_resources:
                try:
                    await robot.set_mode(arm, RES_FIXTURE, "OFF")
                    await robot.release_resource(arm, RES_FIXTURE)
                except Exception:
                    pass

    # Strategy B: Launch both workers concurrently
    # This satisfies the requirement "B launches both workers concurrently using the same acquisition order."
    # The acquisition order (Fixture then Tool) is enforced inside the worker.
    # Since both workers try to acquire Fixture first, one will succeed, then acquire Tool.
    # The other will wait on Fixture, then wait on Tool. This serializes the critical section implicitly.
    
    task_l = asyncio.create_task(worker(ARM_LEFT, POSE_L_HOME, POSE_L_SOURCE, POSE_L_TARGET, POSE_L_DEPART, OBJ_L_PART))
    task_r = asyncio.create_task(worker(ARM_RIGHT, POSE_R_HOME, POSE_R_SOURCE, POSE_R_TARGET, POSE_R_DEPART, OBJ_R_PART))
    
    await asyncio.gather(task_l, task_r)
