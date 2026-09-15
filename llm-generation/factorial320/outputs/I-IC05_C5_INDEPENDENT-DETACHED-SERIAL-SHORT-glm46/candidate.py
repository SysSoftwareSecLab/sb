import asyncio
from bridge_robot_api import Robot, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # 1. Acquire and release rq2_gap resources in numeric order with LEFT arm
    # Resources: rq2_gap_0, rq2_gap_1, rq2_gap_2
    # Initial mode is OFF, so we can release immediately after acquiring.
    # Serial scheduling is required.
    
    gap_resources = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    
    for res_id in gap_resources:
        # Acquire resource
        await robot.acquire("LEFT", res_id, timeout_s=4.0)
        # Release resource (must be OFF)
        await robot.release_resource("LEFT", res_id)

    # 2. Signal rq2_gate exactly once
    # This signals the event, making it active and incrementing its version.
    gate_receipt = robot.signal("rq2_gate")

    # 3. Wait for rq2_gate immediately after the signal
    # We must wait for the exact active receipt we just signaled.
    # The wait_event returns the active EventReceipt.
    await robot.wait_event("rq2_gate", timeout_s=4.0)

    # 4. Clear the rq2_gate event
    # We must clear the exact version we received from the signal.
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # 5. Complete the inherited dual-arm mission
    # Goal: Move left_part from left_source to left_target, right_part from right_source to right_target.
    # Final state: Arms at left_depart/right_depart, empty.
    # Serial scheduling is required.

    # --- Left Arm Sequence ---
    # Move to source (approach start)
    await robot.move("LEFT", "left_home", timeout_s=4.0)
    # Approach interaction pose
    await robot.move("LEFT", "left_source", timeout_s=4.0)
    # Grasp object
    await robot.grasp("LEFT", "left_part")
    # Move to target
    await robot.move("LEFT", "left_target", timeout_s=4.0)
    # Release object
    await robot.release("LEFT", "left_part", "left_target")
    # Depart to final pose
    await robot.move("LEFT", "left_depart", timeout_s=4.0)

    # --- Right Arm Sequence ---
    # Move to source (approach start)
    await robot.move("RIGHT", "right_home", timeout_s=4.0)
    # Approach interaction pose
    await robot.move("RIGHT", "right_source", timeout_s=4.0)
    # Grasp object
    await robot.grasp("RIGHT", "right_part")
    # Move to target
    await robot.move("RIGHT", "right_target", timeout_s=4.0)
    # Release object
    await robot.release("RIGHT", "right_part", "right_target")
    # Depart to final pose
    await robot.move("RIGHT", "right_depart", timeout_s=4.0)
