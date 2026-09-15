import asyncio
from bridge_robot_api import Robot, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # 1. Acquire and release rq2_gap resources in numeric order with LEFT arm
    # Required: "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # Required: "Complete all three rq2_gap resource checks before signalling rq2_gate"
    # Resources start in OFF mode, so no set_mode needed.
    
    gap_ids = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    for rid in gap_ids:
        # Acquire
        await robot.acquire("LEFT", rid, timeout_s=4.0)
        # Release
        await robot.release_resource("LEFT", rid)

    # 2. Signal rq2_gate
    # Required: "Signal rq2_gate exactly once"
    # Required: "wait its exact active receipt exactly once"
    # Required: "clear exactly that version after its assigned protected scope"
    # Required: "wait immediately after the signal"
    
    gate_receipt = robot.signal("rq2_gate")
    
    # Wait immediately after signal
    active_gate_receipt = await robot.wait_event("rq2_gate", timeout_s=4.0)
    
    # 3. Complete inherited dual-arm mission (Serial scheduling)
    # Required: "Use serial scheduling for both the inherited dual-arm mission and the rq2_gate producer/consumer."
    # Required: "Complete and clear the rq2_gate protocol before starting the complete inherited dual-arm mission."
    # Goal: "both parts at their own target; both arms at departure and empty"
    
    # Left Arm Sequence
    # Approach: left_home -> left_source
    await robot.move("LEFT", "left_source")
    # Grasp left_part
    await robot.grasp("LEFT", "left_part")
    # Transport: left_source -> left_target
    await robot.move("LEFT", "left_target")
    # Release left_part at left_target
    await robot.release("LEFT", "left_part", "left_target")
    # Depart: left_target -> left_depart
    await robot.move("LEFT", "left_depart")
    
    # Right Arm Sequence (Serial after Left)
    # Approach: right_home -> right_source
    await robot.move("RIGHT", "right_source")
    # Grasp right_part
    await robot.grasp("RIGHT", "right_part")
    # Transport: right_source -> right_target
    await robot.move("RIGHT", "right_target")
    # Release right_part at right_target
    await robot.release("RIGHT", "right_part", "right_target")
    # Depart: right_target -> right_depart
    await robot.move("RIGHT", "right_depart")
    
    # 4. Clear rq2_gate
    # Required: "clear exactly that version after its assigned protected scope"
    # The protected scope covers the dual-arm mission.
    robot.clear_event("rq2_gate", expected_version=active_gate_receipt.version)
