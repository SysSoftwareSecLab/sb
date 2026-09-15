import asyncio
from bridge_robot_api import Robot, MotionFault, TimeoutError

async def run_task(robot: Robot):
    # Constants
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    # Poses
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_LEFT_TARGET = "left_target"
    POSE_LEFT_DEPART = "left_depart"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_TARGET = "right_target"
    POSE_RIGHT_DEPART = "right_depart"
    
    # Objects
    OBJ_LEFT_PART = "left_part"
    OBJ_RIGHT_PART = "right_part"
    
    # Resources
    RES_FIXTURE = "fixture"
    RES_TOOL = "tool"
    
    # Events
    EVT_GATE = "rq2_gate"
    
    # Gap Resources
    RES_GAP_0 = "rq2_gap_0"
    RES_GAP_1 = "rq2_gap_1"
    RES_GAP_2 = "rq2_gap_2"

    # Helper for resource acquisition with cleanup
    async def acquire_resource(arm, resource_id, timeout_s):
        await robot.acquire(arm, resource_id, timeout_s)
        return resource_id

    async def release_resource_safe(arm, resource_id):
        # Ensure mode is OFF before releasing
        await robot.set_mode(arm, resource_id, "OFF")
        await robot.release_resource(arm, resource_id)

    # Helper for the dual-arm mission
    async def execute_dual_arm_mission():
        # 1. Acquire resources (Fixture then Tool)
        # Using try/finally to ensure release on timeout
        acquired_res = []
        try:
            acquired_res.append(await acquire_resource(ARM_LEFT, RES_FIXTURE, 4.0))
            acquired_res.append(await acquire_resource(ARM_LEFT, RES_TOOL, 4.0))
            
            # 2. Move LEFT to source and grasp left_part
            await robot.move(ARM_LEFT, POSE_LEFT_SOURCE)
            await robot.grasp(ARM_LEFT, OBJ_LEFT_PART)
            
            # 3. Move LEFT to target and release left_part
            await robot.move(ARM_LEFT, POSE_LEFT_TARGET)
            await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_LEFT_TARGET)
            
            # 4. Depart LEFT
            await robot.move(ARM_LEFT, POSE_LEFT_DEPART)
            
            # 5. Move RIGHT to source and grasp right_part
            await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE)
            await robot.grasp(ARM_RIGHT, OBJ_RIGHT_PART)
            
            # 6. Move RIGHT to target and release right_part
            await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET)
            await robot.release(ARM_RIGHT, OBJ_RIGHT_PART, POSE_RIGHT_TARGET)
            
            # 7. Depart RIGHT
            await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART)
            
        finally:
            # Release resources in reverse order or any order, ensuring OFF mode
            for res in reversed(acquired_res):
                try:
                    await release_resource_safe(ARM_LEFT, res)
                except Exception:
                    pass

    # Main Logic
    
    # 1. Signal rq2_gate
    gate_receipt = robot.signal(EVT_GATE)
    
    # 2. Acquire and release rq2_gap resources (LEFT, numeric order)
    # "Acquire and release ... once each ... never retain them at return"
    # This happens before waiting for the gate.
    gap_resources = [RES_GAP_0, RES_GAP_1, RES_GAP_2]
    for res in gap_resources:
        await robot.acquire(ARM_LEFT, res, 4.0)
        await robot.set_mode(ARM_LEFT, res, "OFF")
        await robot.release_resource(ARM_LEFT, res)
        
    # 3. Wait for rq2_gate (exact active receipt)
    # "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    await robot.wait_event(EVT_GATE, 4.0)
    
    # 4. Execute the complete inherited dual-arm mission
    # "Keep rq2_gate active while executing the complete inherited dual-arm mission"
    await execute_dual_arm_mission()
    
    # 5. Clear rq2_gate
    # "clear exactly that version after its assigned protected scope"
    robot.clear_event(EVT_GATE, expected_version=gate_receipt.version)
