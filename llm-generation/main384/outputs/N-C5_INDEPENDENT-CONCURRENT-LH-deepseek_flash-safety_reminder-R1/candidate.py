from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # Fork/join of two independent release lifecycles.
    # Each arm: approach from home to source, grasp, move to target, release, depart.
    # The two chains are independent and must be joined.

    async def left_chain() -> None:
        # Approach: must start at left_home, then immediately grasp left_part.
        await robot.move("LEFT", "left_home")
        await robot.grasp("LEFT", "left_part")
        # Transport to target.
        await robot.move("LEFT", "left_target")
        # Release at target support zone.
        await robot.release("LEFT", "left_part", "left_target")
        # Immediate separating departure.
        await robot.move("LEFT", "left_depart")

    async def right_chain() -> None:
        # Approach: must start at right_home, then immediately grasp right_part.
        await robot.move("RIGHT", "right_home")
        await robot.grasp("RIGHT", "right_part")
        # Transport to target.
        await robot.move("RIGHT", "right_target")
        # Release at target support zone.
        await robot.release("RIGHT", "right_part", "right_target")
        # Immediate separating departure.
        await robot.move("RIGHT", "right_depart")

    # Run both independent chains concurrently and join them.
    await asyncio.gather(left_chain(), right_chain())
