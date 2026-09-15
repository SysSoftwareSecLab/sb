from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    async def left_chain() -> None:
        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "left_target")
        await robot.release("LEFT", "left_part", "left_target")
        await robot.move("LEFT", "left_depart")

    async def right_chain() -> None:
        await robot.move("RIGHT", "right_source")
        await robot.grasp("RIGHT", "right_part")
        await robot.move("RIGHT", "right_target")
        await robot.release("RIGHT", "right_part", "right_target")
        await robot.move("RIGHT", "right_depart")

    left_task = asyncio.create_task(left_chain())
    right_task = asyncio.create_task(right_chain())

    await asyncio.gather(left_task, right_task)
