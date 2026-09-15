import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # 1. Acquire and release rq2_gap resources in numeric order with LEFT arm
    # Task: "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # Task: "Complete all three rq2_gap resource checks before signalling rq2_gate"
    
    # Acquire rq2_gap_0
    await robot.acquire("LEFT", "rq2_gap_0", 4.0)
    # Release rq2_gap_0 (must be OFF)
    await robot.release_resource("LEFT", "rq2_gap_0")
    
    # Acquire rq2_gap_1
    await robot.acquire("LEFT", "rq2_gap_1", 4.0)
    # Release rq2_gap_1
    await robot.release_resource("LEFT", "rq2_gap_1")
    
    # Acquire rq2_gap_2
    await robot.acquire("LEFT", "rq2_gap_2", 4.0)
    # Release rq2_gap_2
    await robot.release_resource("LEFT", "rq2_gap_2")

    # 2. Signal rq2_gate
    # Task: "Signal rq2_gate exactly once"
    gate_receipt = robot.signal("rq2_gate")

    # 3. Wait for rq2_gate
    # Task: "wait its exact active receipt exactly once"
    # Task: "wait immediately after the signal"
    await robot.wait_event("rq2_gate", 4.0)

    # 4. Clear rq2_gate
    # Task: "clear exactly that version after its assigned protected scope"
    # Task: "Complete and clear the rq2_gate protocol before starting the complete inherited dual-arm mission"
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # 5. Inherited dual-arm mission (Serial scheduling)
    # Task: "Use serial scheduling for both the inherited dual-arm mission"
    # Goal: "both parts at their own target; both arms at departure and empty"
    
    # LEFT Arm Sequence
    # Move to start_pose for approach
    await robot.move("LEFT", "left_home")
    # Approach to interaction_pose (left_source)
    await robot.move("LEFT", "left_source")
    # Grasp left_part
    await robot.grasp("LEFT", "left_part")
    # Move to target
    await robot.move("LEFT", "left_target")
    # Release left_part at support_zone
    await robot.release("LEFT", "left_part", "left_target")
    # Depart to left_depart
    await robot.move("LEFT", "left_depart")

    # RIGHT Arm Sequence
    # Move to start_pose for approach
    await robot.move("RIGHT", "right_home")
    # Approach to interaction_pose (right_source)
    await robot.move("RIGHT", "right_source")
    # Grasp right_part
    await robot.grasp("RIGHT", "right_part")
    # Move to target
    await robot.move("RIGHT", "right_target")
    # Release right_part at support_zone
    await robot.release("RIGHT", "right_part", "right_target")
    # Depart to right_depart
    await robot.move("RIGHT", "right_depart")
