import asyncio
from bridge_robot_api import Robot


async def _left_branch(robot: Robot) -> None:
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")


async def _right_branch(robot: Robot) -> None:
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")


async def _consumer(robot: Robot, gate_receipt) -> None:
    await robot.move("RIGHT", "right_home", receipt=gate_receipt)
    clear_event("rq2_gate", expected_version=gate_receipt.version)


async def run_task(robot: Robot) -> None:
    # FOR -> IF -> PAR_JOIN structural shape.
    # FOR: one finite loop iteration.
    for _ in range(1):
        # IF: contains the join (producer + consumer) and the consumer has no mission guard.
        if True:
            # Produce rq2_gate and concurrently join it with the consumer.
            gate_receipt = robot.signal("rq2_gate")
            await asyncio.gather(
                _consumer(robot, gate_receipt),
                _left_branch(robot),
                _right_branch(robot),
            )
            # PAR_JOIN: all branches joined here.
            return
