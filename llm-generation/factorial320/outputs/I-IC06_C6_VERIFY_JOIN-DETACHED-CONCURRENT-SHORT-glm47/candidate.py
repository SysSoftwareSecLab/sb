import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Helper to acquire and release a resource sequentially
    async def check_resource(arm: str, resource_id: str, timeout_s: float):
        await robot.acquire(arm, resource_id, timeout_s)
        await robot.release_resource(arm, resource_id)

    # Phase 1: Resource checks and Gate Protocol
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    # "Complete all three rq2_gap resource checks before signalling rq2_gate"
    await check_resource("LEFT", "rq2_gap_0", 4.0)
    await check_resource("LEFT", "rq2_gap_1", 4.0)
    await check_resource("LEFT", "rq2_gap_2", 4.0)

    # "Signal rq2_gate exactly once"
    gate_receipt = robot.signal("rq2_gate")

    # "wait its exact active receipt exactly once"
    # "wait immediately after the signal"
    # The receipt returned by signal is the active one.
    await robot.wait_event("rq2_gate", 4.0)

    # "clear exactly that version after its assigned protected scope"
    # The protected scope is the gate protocol itself. 
    # We clear immediately after waiting as required by the sequence.
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # Phase 2: Inherited Dual-Arm Mission
    # "Use joined concurrent scheduling for both the inherited dual-arm mission"
    
    async def left_mission():
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

    async def right_mission():
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

    # Run both missions concurrently
    await asyncio.gather(left_mission(), right_mission())
