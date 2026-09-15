import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
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
    
    EVT_GATE = "rq2_gate"
    
    TIMEOUT_ACQUIRE = 4.0
    TIMEOUT_MOVE = 4.0
    TIMEOUT_EVENT = 4.0
    
    # Helper for the complete mission for one arm
    async def worker(arm: str, obj_id: str, home_pose: str, source_pose: str, target_pose: str, depart_pose: str):
        acquired = []
        try:
            # Acquire resources in required order: fixture then tool
            await robot.acquire(arm, RES_FIXTURE, TIMEOUT_ACQUIRE)
            acquired.append(RES_FIXTURE)
            
            await robot.acquire(arm, RES_TOOL, TIMEOUT_ACQUIRE)
            acquired.append(RES_TOOL)
            
            # Move to source
            await robot.move(arm, source_pose, timeout_s=TIMEOUT_MOVE)
            
            # Grasp object
            await robot.grasp(arm, obj_id)
            
            # Move to target
            await robot.move(arm, target_pose, timeout_s=TIMEOUT_MOVE)
            
            # Release object
            await robot.release(arm, obj_id, target_pose)
            
            # Depart immediately
            await robot.move(arm, depart_pose, timeout_s=TIMEOUT_MOVE)
            
        finally:
            # Release resources in reverse order: tool then fixture
            # Ensure mode is OFF before releasing
            if RES_TOOL in acquired:
                await robot.set_mode(arm, RES_TOOL, "OFF")
                await robot.release_resource(arm, RES_TOOL)
            
            if RES_FIXTURE in acquired:
                await robot.set_mode(arm, RES_FIXTURE, "OFF")
                await robot.release_resource(arm, RES_FIXTURE)

    # Structural-OOD shape: FOR -> PAR_JOIN -> consumer IF
    # Variant A: Serial execution of workers.
    # Loop runs once to satisfy the "Inside one finite loop iteration" requirement.
    for _ in range(1):
        # PAR_JOIN: Concurrently join an rq2_gate producer and consumer
        async def producer():
            robot.signal(EVT_GATE)
            
        async def consumer():
            # Wait for the exact active receipt
            receipt = await robot.wait_event(EVT_GATE, TIMEOUT_EVENT)
            
            # Execute the complete inherited mission
            # "A runs the two complete workers serially"
            await worker(ARM_LEFT, OBJ_LEFT, POSE_LEFT_HOME, POSE_LEFT_SOURCE, POSE_LEFT_TARGET, POSE_LEFT_DEPART)
            await worker(ARM_RIGHT, OBJ_RIGHT, POSE_RIGHT_HOME, POSE_RIGHT_SOURCE, POSE_RIGHT_TARGET, POSE_RIGHT_DEPART)
            
            # Clear that version
            robot.clear_event(EVT_GATE, expected_version=receipt.version)
            
        await asyncio.gather(producer(), consumer())

    # Final state check: rq2_gate inactive at return is handled by clear_event.
