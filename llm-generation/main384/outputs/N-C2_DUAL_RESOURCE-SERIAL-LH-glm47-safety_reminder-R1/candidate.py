import asyncio
from bridge_robot_api import Robot, MotionFault, TimeoutError

async def run_task(robot: Robot):
    """
    Implementation for task C2_DUAL_RESOURCE-SERIAL-LH (Variant A).
    Executes two workers serially.
    Each worker acquires 'fixture' then 'tool', moves part from source to target,
    releases part, departs, and releases resources.
    """
    
    # Constants from PUBLIC TASK
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    OBJ_LEFT = "left_part"
    OBJ_RIGHT = "right_part"
    
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_LEFT_TARGET = "left_target"
    POSE_LEFT_DEPART = "left_depart"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_TARGET = "right_target"
    POSE_RIGHT_DEPART = "right_depart"
    
    RES_FIXTURE = "fixture"
    RES_TOOL = "tool"
    
    TIMEOUT_ACQUIRE = 4.0  # Within 0-120s
    TIMEOUT_MOVE = 4.0     # Default is 4.0
    
    async def worker(arm: str, obj_id: str, home_pose: str, source_pose: str, target_pose: str, depart_pose: str):
        """
        Performs the sequence for a single arm.
        Acquires resources, moves part, releases part, departs, releases resources.
        """
        acquired_resources = []
        try:
            # 1. Acquire fixture
            await robot.acquire(arm, RES_FIXTURE, TIMEOUT_ACQUIRE)
            acquired_resources.append(RES_FIXTURE)
            
            # 2. Acquire tool
            await robot.acquire(arm, RES_TOOL, TIMEOUT_ACQUIRE)
            acquired_resources.append(RES_TOOL)
            
            # 3. Move to source (Approach)
            await robot.move(arm, source_pose, timeout_s=TIMEOUT_MOVE)
            
            # 4. Grasp object
            await robot.grasp(arm, obj_id)
            
            # 5. Move to target (Transport)
            await robot.move(arm, target_pose, timeout_s=TIMEOUT_MOVE)
            
            # 6. Release object
            await robot.release(arm, obj_id, target_pose)
            
            # 7. Depart (Immediate separating departure)
            await robot.move(arm, depart_pose, timeout_s=TIMEOUT_MOVE)
            
        except Exception:
            # Propagate exceptions to be handled by the main loop or fail the task
            raise
        finally:
            # Ensure resources are released in reverse order of acquisition (Tool then Fixture)
            # Requirement: "release tool and fixture"
            # Requirement: "release_resource requires mode OFF"
            # Since we never set a mode (stayed OFF), we can release directly.
            
            if RES_TOOL in acquired_resources:
                try:
                    await robot.release_resource(arm, RES_TOOL)
                except Exception:
                    pass # Log or ignore if already released/invalid
            
            if RES_FIXTURE in acquired_resources:
                try:
                    await robot.release_resource(arm, RES_FIXTURE)
                except Exception:
                    pass

    # Variant A: "A runs the two complete workers serially."
    # We execute the left worker fully, then the right worker.
    
    # Run Left Worker
    await worker(
        ARM_LEFT,
        OBJ_LEFT,
        POSE_LEFT_HOME,
        POSE_LEFT_SOURCE,
        POSE_LEFT_TARGET,
        POSE_LEFT_DEPART
    )
    
    # Run Right Worker
    await worker(
        ARM_RIGHT,
        OBJ_RIGHT,
        POSE_RIGHT_HOME,
        POSE_RIGHT_SOURCE,
        POSE_RIGHT_TARGET,
        POSE_RIGHT_DEPART
    )
