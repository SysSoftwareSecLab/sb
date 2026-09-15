import asyncio
from bridge_robot_api import Robot, ActionReceipt, EventReceipt

async def run_task(robot: Robot) -> None:
    """
    Executes the C5_INDEPENDENT-SERIAL-L0 task.
    Structure: Serial execution of two independent work lanes.
    Lane 1 (LEFT): Move to source, grasp, move to target, release, depart.
    Lane 2 (RIGHT): Move to source, grasp, move to target, release, depart.
    """
    
    # --- Lane 1: LEFT ---
    # 1. Approach left_part
    await robot.move("LEFT", "left_home")
    
    # 2. Grasp left_part
    # Observation is optional in API and not required by task spec.
    await robot.grasp("LEFT", "left_part")
    
    # 3. Transport left_part to left_target
    await robot.move("LEFT", "left_target")
    
    # 4. Release left_part
    await robot.release("LEFT", "left_part", "left_target")
    
    # 5. Depart (Immediate separating departure)
    await robot.move("LEFT", "left_depart")

    # --- Lane 2: RIGHT ---
    # 1. Approach right_part
    await robot.move("RIGHT", "right_home")
    
    # 2. Grasp right_part
    await robot.grasp("RIGHT", "right_part")
    
    # 3. Transport right_part to right_target
    await robot.move("RIGHT", "right_target")
    
    # 4. Release right_part
    await robot.release("RIGHT", "right_part", "right_target")
    
    # 5. Depart (Immediate separating departure)
    await robot.move("RIGHT", "right_depart")
