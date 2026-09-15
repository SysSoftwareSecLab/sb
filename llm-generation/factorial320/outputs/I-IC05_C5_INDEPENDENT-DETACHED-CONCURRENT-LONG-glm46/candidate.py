import asyncio
from bridge_robot_api import Robot

async def run_task(robot: Robot):
    # 1. Signal rq2_gate
    gate_receipt = robot.signal("rq2_gate")
    
    # 2. Acquire and release resources rq2_gap_0, rq2_gap_1, rq2_gap_2 with LEFT arm
    # in numeric order.
    # Acquire timeout set to 1.0s (within 0-120s range).
    # Mode is OFF (initial mode), so no set_mode needed.
    for res_id in ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]:
        await robot.acquire("LEFT", res_id, timeout_s=1.0)
        await robot.release_resource("LEFT", res_id)
    
    # 3. Wait for the exact active receipt of rq2_gate
    # Timeout set to 1.0s.
    await robot.wait_event("rq2_gate", timeout_s=1.0)
    
    # 4. Clear the event using the version from the receipt
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
    
    # 5. Execute the dual-arm mission concurrently
    # LEFT: left_home -> left_source -> grasp -> left_target -> release -> left_depart
    # RIGHT: right_home -> right_source -> grasp -> right_target -> release -> right_depart
    
    async def left_arm_mission():
        # Move to source
        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "left_source")
        # Grasp
        await robot.grasp("LEFT", "left_part")
        # Move to target
        await robot.move("LEFT", "left_target")
        # Release
        await robot.release("LEFT", "left_part", "left_target")
        # Depart
        await robot.move("LEFT", "left_depart")
        
    async def right_arm_mission():
        # Move to source
        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", "right_source")
        # Grasp
        await robot.grasp("RIGHT", "right_part")
        # Move to target
        await robot.move("RIGHT", "right_target")
        # Release
        await robot.release("RIGHT", "right_part", "right_target")
        # Depart
        await robot.move("RIGHT", "right_depart")
        
    # Run both missions concurrently
    await asyncio.gather(left_arm_mission(), right_arm_mission())
