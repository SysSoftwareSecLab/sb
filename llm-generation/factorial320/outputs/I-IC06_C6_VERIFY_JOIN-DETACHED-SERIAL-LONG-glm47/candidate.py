import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # 1. Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # 2. Acquire and release rq2_gap resources in numeric order with LEFT
    #    Using serial scheduling as required.
    for res_id in ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]:
        await robot.acquire("LEFT", res_id, timeout_s=4.0)
        await robot.release_resource("LEFT", res_id)
    
    # 3. Wait for rq2_gate (exact active receipt)
    #    The receipt we signaled is now active.
    await robot.wait_event("rq2_gate", timeout_s=4.0)
    
    # 4. Clear rq2_gate protocol
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
    
    # 5. Inherited dual-arm mission (Serial scheduling)
    #    LEFT Arm: Move to source, grasp, move to target, release, depart
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")
    
    #    RIGHT Arm: Move to source, grasp, move to target, release, depart
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
