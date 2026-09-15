import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants derived from PUBLIC TASK
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
    
    EVENT_GATE = "rq2_gate"
    
    TIMEOUT_ACQUIRE = 4.0
    TIMEOUT_WAIT = 4.0
    TIMEOUT_MOVE = 4.0
    
    # Helper for resource acquisition with cleanup on timeout
    async def acquire_with_cleanup(arm: str, resource_id: str, timeout_s: float, acquired_list: list):
        try:
            receipt = await robot.acquire(arm, resource_id, timeout_s)
            acquired_list.append(resource_id)
            return receipt
        except TimeoutError:
            # Release any resources acquired in this batch so far
            for res in acquired_list:
                await robot.release_resource(arm, res)
            raise

    # --- Phase 1: RQ2 Gate Protocol (Serial) ---
    # "Signal rq2_gate exactly once, wait its exact active receipt exactly once, and clear exactly that version"
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate"
    
    # 1. Signal the gate
    gate_receipt = robot.signal(EVENT_GATE)
    
    # 2. Acquire and release gaps 0, 1, 2 serially with LEFT
    # "never retain them at return"
    for gap_id in [RES_GAP_0, RES_GAP_1, RES_GAP_2]:
        await robot.acquire(ARM_LEFT, gap_id, TIMEOUT_ACQUIRE)
        await robot.release_resource(ARM_LEFT, gap_id)
        
    # 3. Wait for the gate
    # "wait its exact active receipt exactly once"
    # The receipt returned by wait_event must match the one we signaled (version match)
    active_gate_receipt = await robot.wait_event(EVENT_GATE, TIMEOUT_WAIT)
    
    # 4. Clear the event
    # "clear exactly that version after its assigned protected scope"
    # The scope was the gap checks. Now we clear.
    robot.clear_event(EVENT_GATE, expected_version=active_gate_receipt.version)
    
    # --- Phase 2: Inherited Dual-Arm Mission (Serial) ---
    # "A runs the two complete workers serially"
    # "Acquire fixture then tool, carry the corresponding part to target while owning both, release and depart, then release tool and fixture"
    
    async def run_worker(arm: str, home_pose: str, source_pose: str, target_pose: str, depart_pose: str, part_id: str):
        acquired = []
        
        # Acquire resources (Fixture then Tool)
        # Use try/finally for cleanup on timeout as requested
        await acquire_with_cleanup(arm, RES_FIXTURE, TIMEOUT_ACQUIRE, acquired)
        await acquire_with_cleanup(arm, RES_TOOL, TIMEOUT_ACQUIRE, acquired)
        
        try:
            # Move to source (Approach)
            await robot.move(arm, source_pose, timeout_s=TIMEOUT_MOVE)
            
            # Grasp part
            # No observation required by task spec for grasp
            await robot.grasp(arm, part_id)
            
            # Move to target
            await robot.move(arm, target_pose, timeout_s=TIMEOUT_MOVE)
            
            # Release part
            await robot.release(arm, part_id, target_pose)
            
            # Depart (Immediate separating departure)
            await robot.move(arm, depart_pose, timeout_s=TIMEOUT_MOVE)
            
        finally:
            # Release resources (Tool then Fixture, though order not strictly specified, reverse is good practice)
            # "release tool and fixture"
            if RES_TOOL in acquired:
                await robot.release_resource(arm, RES_TOOL)
            if RES_FIXTURE in acquired:
                await robot.release_resource(arm, RES_FIXTURE)

    # Run LEFT worker
    await run_worker(
        ARM_LEFT, 
        POSE_LEFT_HOME, POSE_LEFT_SOURCE, POSE_LEFT_TARGET, POSE_LEFT_DEPART, 
        OBJ_LEFT_PART
    )
    
    # Run RIGHT worker
    await run_worker(
        ARM_RIGHT, 
        POSE_RIGHT_HOME, POSE_RIGHT_SOURCE, POSE_RIGHT_TARGET, POSE_RIGHT_DEPART, 
        OBJ_RIGHT_PART
    )
