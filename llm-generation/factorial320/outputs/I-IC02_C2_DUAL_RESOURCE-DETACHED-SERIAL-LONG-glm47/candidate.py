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

    # --- RQ2 Gate Protocol (Serial) ---
    # 1. Signal rq2_gate exactly once
    gate_receipt = robot.signal(EVENT_GATE)
    
    # 2. Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order
    # Use try/finally for resource safety as required
    for gap_res in [RES_GAP_0, RES_GAP_1, RES_GAP_2]:
        try:
            await robot.acquire(ARM_LEFT, gap_res, TIMEOUT_ACQUIRE)
        except TimeoutError:
            # If acquisition fails, we cannot proceed with the protocol as intended.
            # The requirement says "Use try/finally so an acquisition timeout releases every successfully acquired controller."
            # Since we release immediately in finally, we just re-raise or break.
            raise
        finally:
            # Release immediately after acquisition (check)
            await robot.release_resource(ARM_LEFT, gap_res)
            
    # 3. Wait for rq2_gate exactly once (using the receipt we just signaled)
    # The requirement says "wait its exact active receipt exactly once"
    # Since we just signaled it, it should be active.
    await robot.wait_event(EVENT_GATE, TIMEOUT_WAIT)
    
    # 4. Clear rq2_gate exactly that version
    robot.clear_event(EVENT_GATE, expected_version=gate_receipt.version)

    # --- Inherited Dual-Arm Mission (Serial) ---
    # "A runs the two complete workers serially."
    
    async def run_worker(arm: str, home_pose: str, source_pose: str, target_pose: str, depart_pose: str, part_id: str):
        # Acquire fixture then tool
        # Use try/finally for resource safety
        try:
            await robot.acquire(arm, RES_FIXTURE, TIMEOUT_ACQUIRE)
            await robot.acquire(arm, RES_TOOL, TIMEOUT_ACQUIRE)
            
            # Move to source (Approach)
            await robot.move(arm, source_pose, TIMEOUT_MOVE)
            
            # Grasp part
            await robot.grasp(arm, part_id)
            
            # Move to target
            await robot.move(arm, target_pose, TIMEOUT_MOVE)
            
            # Release part
            await robot.release(arm, part_id, target_pose)
            
            # Depart (Immediate separating departure)
            await robot.move(arm, depart_pose, TIMEOUT_MOVE)
            
        finally:
            # Release tool and fixture in finally block
            # Order not strictly specified for release, but reverse of acquire is logical
            # Must ensure we own them to release. If acquire failed, this might raise, 
            # but the requirement implies releasing "successfully acquired" ones.
            # We check ownership implicitly by calling release; if not owned, it might fail, 
            # but the spec says "release tool and fixture" at end.
            # Given the strict "Use try/finally" instruction, we wrap the releases.
            
            # Check if we own tool before releasing? 
            # The API doesn't have a check. We assume if we reached here, we might own them.
            # If acquire failed, we shouldn't release.
            # However, simple try/finally structure usually assumes we acquired them or handles the error.
            # Given the simplicity, we just release.
            
            try:
                await robot.release_resource(arm, RES_TOOL)
            except Exception:
                pass # Ignore if not owned or already released
            
            try:
                await robot.release_resource(arm, RES_FIXTURE)
            except Exception:
                pass

    # Run Left Worker
    await run_worker(ARM_LEFT, POSE_LEFT_HOME, POSE_LEFT_SOURCE, POSE_LEFT_TARGET, POSE_LEFT_DEPART, OBJ_LEFT_PART)
    
    # Run Right Worker
    await run_worker(ARM_RIGHT, POSE_RIGHT_HOME, POSE_RIGHT_SOURCE, POSE_RIGHT_TARGET, POSE_RIGHT_DEPART, OBJ_RIGHT_PART)
