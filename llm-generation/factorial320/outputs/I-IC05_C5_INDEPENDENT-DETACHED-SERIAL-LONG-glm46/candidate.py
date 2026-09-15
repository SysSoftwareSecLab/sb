import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # 1. Signal rq2_gate
    # "Signal rq2_gate exactly once"
    gate_receipt = robot.signal("rq2_gate")
    
    # 2. Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 with LEFT, in numeric order
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # "never retain them at return"
    # "complete all three rq2_gap resource checks, and only then wait for rq2_gate"
    # "Use serial scheduling"
    
    # Resource 0
    await robot.acquire("LEFT", "rq2_gap_0", timeout_s=4.0)
    await robot.release_resource("LEFT", "rq2_gap_0")
    
    # Resource 1
    await robot.acquire("LEFT", "rq2_gap_1", timeout_s=4.0)
    await robot.release_resource("LEFT", "rq2_gap_1")
    
    # Resource 2
    await robot.acquire("LEFT", "rq2_gap_2", timeout_s=4.0)
    await robot.release_resource("LEFT", "rq2_gap_2")
    
    # 3. Wait for rq2_gate
    # "wait its exact active receipt exactly once"
    # "only then wait for rq2_gate"
    # "clear exactly that version after its assigned protected scope"
    wait_receipt = await robot.wait_event("rq2_gate", timeout_s=4.0)
    
    # 4. Clear rq2_gate
    # "clear exactly that version after its assigned protected scope"
    # "Complete and clear the rq2_gate protocol before starting the complete inherited dual-arm mission"
    robot.clear_event("rq2_gate", expected_version=wait_receipt.version)
    
    # 5. Inherited dual-arm mission (Serial)
    # "Use serial scheduling for both the inherited dual-arm mission"
    # "both parts at their own target; both arms at departure and empty"
    
    # LEFT Arm Sequence
    # Approach (move to start_pose)
    await robot.move("LEFT", "left_home", timeout_s=4.0)
    # Grasp
    await robot.grasp("LEFT", "left_part")
    # Move to target
    await robot.move("LEFT", "left_target", timeout_s=4.0)
    # Release
    await robot.release("LEFT", "left_part", "left_target")
    # Depart (immediate separating departure)
    await robot.move("LEFT", "left_depart", timeout_s=4.0)
    
    # RIGHT Arm Sequence
    # Approach (move to start_pose)
    await robot.move("RIGHT", "right_home", timeout_s=4.0)
    # Grasp
    await robot.grasp("RIGHT", "right_part")
    # Move to target
    await robot.move("RIGHT", "right_target", timeout_s=4.0)
    # Release
    await robot.release("RIGHT", "right_part", "right_target")
    # Depart (immediate separating departure)
    await robot.move("RIGHT", "right_depart", timeout_s=4.0)
