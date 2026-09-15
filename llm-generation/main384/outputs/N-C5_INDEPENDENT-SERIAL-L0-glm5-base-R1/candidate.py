import asyncio

try:
    from bridge_robot_api import MotionFault
except Exception:
    MotionFault = None


async def _left_chain(robot):
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")


async def _right_chain(robot):
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")


async def run_task(robot):
    await asyncio.gather(_left_chain(robot), _right_chain(robot))
