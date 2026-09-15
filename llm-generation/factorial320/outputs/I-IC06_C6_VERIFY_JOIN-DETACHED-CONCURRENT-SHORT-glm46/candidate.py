import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Phase 1: Resource Checks and Gate Protocol
    # Acquire rq2_gap_0, rq2_gap_1, rq2_gap_2 in numeric order with LEFT arm
    await robot.acquire("LEFT", "rq2_gap_0", 4.0)
    await robot.acquire("LEFT", "rq2_gap_1", 4.0)
    await robot.acquire("LEFT", "rq2_gap_2", 4.0)

    # Release resources in numeric order
    await robot.release_resource("LEFT", "rq2_gap_0")
    await robot.release_resource("LEFT", "rq2_gap_1")
    await robot.release_resource("LEFT", "rq2_gap_2")

    # Signal rq2_gate exactly once
    gate_receipt = robot.signal("rq2_gate")

    # Wait for rq2_gate immediately after signal
    # The receipt returned by signal is active, so wait_event should return it or a newer one.
    # Given the requirement "wait its exact active receipt exactly once", we wait for the event.
    # Note: wait_event returns the active receipt.
    await robot.wait_event("rq2_gate", 4.0)

    # Clear the event using the version from the receipt we obtained
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # Phase 2: Concurrent Dual-Arm Mission
    # Both arms move from home to source, grasp, move to target, release, move to depart.
    
    async def left_arm_task():
        # Move to source
        await robot.move("LEFT", "left_source")
        # Grasp part
        await robot.grasp("LEFT", "left_part")
        # Move to target
        await robot.move("LEFT", "left_target")
        # Release part
        await robot.release("LEFT", "left_part", "left_target")
        # Move to depart
        await robot.move("LEFT", "left_depart")

    async def right_arm_task():
        # Move to source
        await robot.move("RIGHT", "right_source")
        # Grasp part
        await robot.grasp("RIGHT", "right_part")
        # Move to target
        await robot.move("RIGHT", "right_target")
        # Release part
        await robot.release("RIGHT", "right_part", "right_target")
        # Move to depart
        await robot.move("RIGHT", "right_depart")

    # Run tasks concurrently
    await asyncio.gather(left_arm_task(), right_arm_task())
