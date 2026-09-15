import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot) -> None:
    """
    Executes the C6_VERIFY_JOIN-SERIAL-L0 task.
    
    Structure:
    1. LEFT branch: Move to source, grasp left_part, inspect left_verification, move to target, release.
    2. RIGHT branch: Move to source, grasp right_part, inspect right_verification, move to target, release.
    3. Join: Wait for both 'left_ready' and 'right_ready' events before proceeding to departure.
    4. Departure: Both arms move to their respective departure poses.
    
    This implements the SERIAL concurrency constraint by awaiting the LEFT branch
    completion before starting the RIGHT branch, ensuring strict serialization.
    """
    
    # --- LEFT BRANCH ---
    # 1. Move to source
    await robot.move("LEFT", "left_home", timeout_s=4)
    # 2. Grasp left_part
    await robot.grasp("LEFT", "left_part")
    # 3. Inspect left_verification
    await robot.inspect("LEFT", "left_verification")
    # 4. Move to target
    await robot.move("LEFT", "left_target", timeout_s=4)
    # 5. Release left_part at left_target
    await robot.release("LEFT", "left_part", "left_target")
    # 6. Signal left_ready
    robot.signal("left_ready", "left_part")
    
    # --- RIGHT BRANCH (Serial execution after LEFT) ---
    # 1. Move to source
    await robot.move("RIGHT", "right_home", timeout_s=4)
    # 2. Grasp right_part
    await robot.grasp("RIGHT", "right_part")
    # 3. Inspect right_verification
    await robot.inspect("RIGHT", "right_verification")
    # 4. Move to target
    await robot.move("RIGHT", "right_target", timeout_s=4)
    # 5. Release right_part at right_target
    await robot.release("RIGHT", "right_part", "right_target")
    # 6. Signal right_ready
    robot.signal("right_ready", "right_part")
    
    # --- JOIN PHASE ---
    # Wait for both events to be signaled (joining point)
    # Using asyncio.gather to wait for both events concurrently at the join point
    await asyncio.gather(
        robot.wait_event("left_ready", timeout_s=30),
        robot.wait_event("right_ready", timeout_s=30)
    )
    
    # --- DEPARTURE PHASE ---
    # Both arms move to departure poses
    await asyncio.gather(
        robot.move("LEFT", "left_depart", timeout_s=4),
        robot.move("RIGHT", "right_depart", timeout_s=4)
    )
