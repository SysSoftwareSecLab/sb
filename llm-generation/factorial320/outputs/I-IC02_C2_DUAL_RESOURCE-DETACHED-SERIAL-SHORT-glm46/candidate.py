import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_LEFT_TARGET = "left_target"
    POSE_LEFT_DEPART = "left_depart"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_TARGET = "right_target"
    POSE_RIGHT_DEPART = "right_depart"
    
    OBJ_LEFT_PART = "left_part"
    OBJ_RIGHT_PART = "right_part"
    
    RES_FIXTURE = "fixture"
    RES_TOOL = "tool"
    
    RES_GAP_0 = "rq2_gap_0"
    RES_GAP_1 = "rq2_gap_1"
    RES_GAP_2 = "rq2_gap_2"
    
    EVT_GATE = "rq2_gate"
    
    TIMEOUT_ACQUIRE = 4.0
    TIMEOUT_WAIT = 4.0

    # --- RQ2 Gate Protocol ---
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # "Complete all three rq2_gap resource checks before signalling rq2_gate"
    
    async def acquire_gap(res_id: str):
        try:
            await robot.acquire(ARM_LEFT, res_id, TIMEOUT_ACQUIRE)
        except TimeoutError:
            raise
        finally:
            # "never retain them at return"
            await robot.release_resource(ARM_LEFT, res_id)

    # Serial execution of gap checks
    await acquire_gap(RES_GAP_0)
    await acquire_gap(RES_GAP_1)
    await acquire_gap(RES_GAP_2)
    
    # "Signal rq2_gate exactly once"
    gate_receipt = robot.signal(EVT_GATE)
    
    # "wait its exact active receipt exactly once"
    # "wait immediately after the signal"
    active_gate_receipt = await robot.wait_event(EVT_GATE, TIMEOUT_WAIT)
    
    # Protected scope for the gate protocol
    try:
        # "Complete and clear the rq2_gate protocol before starting the complete inherited dual-arm mission."
        # The inherited mission starts after this block.
        pass
    finally:
        # "clear exactly that version after its assigned protected scope"
        robot.clear_event(EVT_GATE, expected_version=active_gate_receipt.version)

    # --- Inherited Dual-Arm Mission ---
    # "A runs the two complete workers serially."
    # "Acquire fixture then tool, carry the corresponding part to target while owning both, release and depart, then release tool and fixture."
    
    async def run_worker(arm: str, home_pose: str, source_pose: str, target_pose: str, depart_pose: str, part_id: str):
        acquired_resources = []
        try:
            # Acquire resources
            await robot.acquire(arm, RES_FIXTURE, TIMEOUT_ACQUIRE)
            acquired_resources.append(RES_FIXTURE)
            
            await robot.acquire(arm, RES_TOOL, TIMEOUT_ACQUIRE)
            acquired_resources.append(RES_TOOL)
            
            # Move to source
            await robot.move(arm, source_pose)
            
            # Grasp part
            await robot.grasp(arm, part_id)
            
            # Move to target
            await robot.move(arm, target_pose)
            
            # Release part
            await robot.release(arm, part_id, target_pose)
            
            # Depart immediately
            await robot.move(arm, depart_pose)
            
        finally:
            # Release resources in reverse order (tool then fixture) or any order, ensuring OFF
            # "release tool and fixture"
            # release_resource requires mode OFF. set_mode to OFF.
            for res in reversed(acquired_resources):
                await robot.set_mode(arm, res, "OFF")
                await robot.release_resource(arm, res)

    # Run Left Worker
    await run_worker(
        ARM_LEFT, POSE_LEFT_HOME, POSE_LEFT_SOURCE, POSE_LEFT_TARGET, POSE_LEFT_DEPART, OBJ_LEFT_PART
    )
    
    # Run Right Worker
    await run_worker(
        ARM_RIGHT, POSE_RIGHT_HOME, POSE_RIGHT_SOURCE, POSE_RIGHT_TARGET, POSE_RIGHT_DEPART, OBJ_RIGHT_PART
    )
