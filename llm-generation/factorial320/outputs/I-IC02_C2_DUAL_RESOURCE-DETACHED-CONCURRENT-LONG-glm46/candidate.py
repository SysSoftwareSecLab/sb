import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    OBJ_LEFT = "left_part"
    OBJ_RIGHT = "right_part"
    RES_FIXTURE = "fixture"
    RES_TOOL = "tool"
    RES_GAP_0 = "rq2_gap_0"
    RES_GAP_1 = "rq2_gap_1"
    RES_GAP_2 = "rq2_gap_2"
    EVT_GATE = "rq2_gate"
    
    POSE_L_HOME = "left_home"
    POSE_R_HOME = "right_home"
    POSE_L_SOURCE = "left_source"
    POSE_R_SOURCE = "right_source"
    POSE_L_TARGET = "left_target"
    POSE_R_TARGET = "right_target"
    POSE_L_DEPART = "left_depart"
    POSE_R_DEPART = "right_depart"
    
    TIMEOUT_ACQ = 4.0
    TIMEOUT_WAIT = 4.0

    # --- Helper: Resource Acquisition with Cleanup ---
    async def acquire_resource(arm: str, resource_id: str, timeout: float):
        await robot.acquire(arm, resource_id, timeout)

    # --- Phase 1: RQ2 Gate Protocol ---
    # "Signal rq2_gate exactly once, wait its exact active receipt exactly once, and clear exactly that version after its assigned protected scope."
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order; never retain them at return."
    # "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    
    # 1. Signal the gate
    gate_receipt = robot.signal(EVT_GATE)
    
    # 2. Concurrently check gaps (acquire and release) while the gate is active
    # "Use joined concurrent scheduling for both the inherited dual-arm mission and the rq2_gate producer/consumer."
    async def check_gap(res_id: str):
        # Acquire
        await robot.acquire(ARM_LEFT, res_id, TIMEOUT_ACQ)
        # Release
        await robot.release_resource(ARM_LEFT, res_id)

    # Run gap checks concurrently
    await asyncio.gather(
        check_gap(RES_GAP_0),
        check_gap(RES_GAP_1),
        check_gap(RES_GAP_2)
    )
    
    # 3. Wait for the gate (consume the signal)
    # "only then wait for rq2_gate"
    await robot.wait_event(EVT_GATE, TIMEOUT_WAIT)
    
    # 4. Clear the event
    # "clear exactly that version after its assigned protected scope"
    robot.clear_event(EVT_GATE, expected_version=gate_receipt.version)

    # --- Phase 2: Inherited Dual-Arm Mission ---
    # "A runs the two complete workers serially. B launches both workers concurrently using the same acquisition order."
    # "Acquire fixture then tool, carry the corresponding part to target while owning both, release and depart, then release tool and fixture."
    # "Use try/finally so an acquisition timeout releases every successfully acquired controller."
    
    async def worker(arm: str, obj_id: str, home_pose: str, source_pose: str, target_pose: str, depart_pose: str):
        acquired = []
        try:
            # Acquire fixture then tool
            await robot.acquire(arm, RES_FIXTURE, TIMEOUT_ACQ)
            acquired.append(RES_FIXTURE)
            await robot.acquire(arm, RES_TOOL, TIMEOUT_ACQ)
            acquired.append(RES_TOOL)
            
            # Move to source (Approach)
            await robot.move(arm, source_pose)
            
            # Grasp
            await robot.grasp(arm, obj_id)
            
            # Move to target
            await robot.move(arm, target_pose)
            
            # Release
            await robot.release(arm, obj_id, target_pose)
            
            # Depart (Immediate separating departure)
            await robot.move(arm, depart_pose)
            
        finally:
            # Release resources in reverse order (tool then fixture) or just ensure all released
            # "release tool and fixture"
            for res in reversed(acquired):
                try:
                    await robot.release_resource(arm, res)
                except Exception:
                    pass

    # Launch both workers concurrently
    await asyncio.gather(
        worker(ARM_LEFT, OBJ_LEFT, POSE_L_HOME, POSE_L_SOURCE, POSE_L_TARGET, POSE_L_DEPART),
        worker(ARM_RIGHT, OBJ_RIGHT, POSE_R_HOME, POSE_R_SOURCE, POSE_R_TARGET, POSE_R_DEPART)
    )
