import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_SOURCE = "left_source"
    LEFT_TARGET = "left_target"
    LEFT_DEPART = "left_depart"
    
    RIGHT_HOME = "right_home"
    RIGHT_SOURCE = "right_source"
    RIGHT_TARGET = "right_target"
    RIGHT_DEPART = "right_depart"
    
    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    RQ2_GATE = "rq2_gate"
    
    # Resources
    GAP_0 = "rq2_gap_0"
    GAP_1 = "rq2_gap_1"
    GAP_2 = "rq2_gap_2"
    
    # Facts
    LEFT_VERIFICATION = "left_verification"
    RIGHT_VERIFICATION = "right_verification"

    # --- Phase 1: Concurrent Verification ---
    
    async def verify_left():
        # Approach
        await robot.move(LEFT, LEFT_SOURCE)
        # Grasp
        obs = await robot.grasp(LEFT, LEFT_PART)
        # Inspect
        await robot.inspect(LEFT, LEFT_VERIFICATION)
        # Release
        await robot.release(LEFT, LEFT_PART, LEFT_SOURCE)
        # Depart
        await robot.move(LEFT, LEFT_HOME)
        # Signal Ready
        robot.signal(LEFT_READY)

    async def verify_right():
        # Approach
        await robot.move(RIGHT, RIGHT_SOURCE)
        # Grasp
        obs = await robot.grasp(RIGHT, RIGHT_PART)
        # Inspect
        await robot.inspect(RIGHT, RIGHT_VERIFICATION)
        # Release
        await robot.release(RIGHT, RIGHT_PART, RIGHT_SOURCE)
        # Depart
        await robot.move(RIGHT, RIGHT_HOME)
        # Signal Ready
        robot.signal(RIGHT_READY)

    # Run verification concurrently
    await asyncio.gather(verify_left(), verify_right())

    # --- Phase 2: Gate Producer ---
    
    # Signal rq2_gate exactly once
    robot.signal(RQ2_GATE)

    # --- Phase 3: Resource Checks (LEFT only, numeric order) ---
    
    # Acquire and release rq2_gap_0
    await robot.acquire(LEFT, GAP_0, 120.0)
    await robot.release_resource(LEFT, GAP_0)
    
    # Acquire and release rq2_gap_1
    await robot.acquire(LEFT, GAP_1, 120.0)
    await robot.release_resource(LEFT, GAP_1)
    
    # Acquire and release rq2_gap_2
    await robot.acquire(LEFT, GAP_2, 120.0)
    await robot.release_resource(LEFT, GAP_2)

    # --- Phase 4: Wait for Gate ---
    
    # Wait for rq2_gate to be active
    gate_receipt = await robot.wait_event(RQ2_GATE, 120.0)

    # --- Phase 5: Inherited Dual-Arm Mission (Concurrent) ---
    # Goal: Move parts to target, arms to depart.
    # rq2_gate must remain active during this phase.

    async def mission_left():
        # Approach
        await robot.move(LEFT, LEFT_SOURCE)
        # Grasp
        await robot.grasp(LEFT, LEFT_PART)
        # Move to Target
        await robot.move(LEFT, LEFT_TARGET)
        # Release
        await robot.release(LEFT, LEFT_PART, LEFT_TARGET)
        # Depart
        await robot.move(LEFT, LEFT_DEPART)

    async def mission_right():
        # Approach
        await robot.move(RIGHT, RIGHT_SOURCE)
        # Grasp
        await robot.grasp(RIGHT, RIGHT_PART)
        # Move to Target
        await robot.move(RIGHT, RIGHT_TARGET)
        # Release
        await robot.release(RIGHT, RIGHT_PART, RIGHT_TARGET)
        # Depart
        await robot.move(RIGHT, RIGHT_DEPART)

    # Run mission concurrently
    await asyncio.gather(mission_left(), mission_right())

    # --- Phase 6: Clear Gate ---
    
    # Clear rq2_gate using the exact version obtained from wait_event
    robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)
