import asyncio
from bridge_robot_api import Robot

async def run_task(robot: Robot):
    """
    Executes the C5_INDEPENDENT-SERIAL-LH task.
    Structure: Serial execution of two independent work lanes (LEFT then RIGHT).
    Goal: Move left_part to left_target and right_part to right_target,
          then move arms to left_depart and right_depart respectively.
    """

    # --- LEFT LANE ---
    # 1. Approach left_part
    await robot.move("LEFT", "left_source")
    # 2. Grasp left_part
    await robot.grasp("LEFT", "left_part")
    # 3. Transport left_part to left_target
    await robot.move("LEFT", "left_target")
    # 4. Release left_part at left_target
    await robot.release("LEFT", "left_part", "left_target")
    # 5. Depart to left_depart
    await robot.move("LEFT", "left_depart")

    # --- RIGHT LANE ---
    # 1. Approach right_part
    await robot.move("RIGHT", "right_source")
    # 2. Grasp right_part
    await robot.grasp("RIGHT", "right_part")
    # 3. Transport right_part to right_target
    await robot.move("RIGHT", "right_target")
    # 4. Release right_part at right_target
    await robot.release("RIGHT", "right_part", "right_target")
    # 5. Depart to right_depart
    await robot.move("RIGHT", "right_depart")
