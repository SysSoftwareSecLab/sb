import asyncio

from bridge_robot_api import Robot


async def _left_branch(robot: Robot) -> None:
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")
    robot.signal("left_ready")


async def _right_branch(robot: Robot) -> None:
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
    robot.signal("right_ready")


async def _consumer(robot: Robot, gate_receipt) -> None:
    await robot.wait_event("rq2_gate", 5)
    await _left_branch(robot)
    await _right_branch(robot)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)


async def _producer() -> None:
    robot.signal("rq2_gate")


async def run_task(robot: Robot) -> None:
    for _ in range(1):
        gate_receipt = robot.signal("rq2_gate")
        producer = asyncio.create_task(_producer())
        consumer = asyncio.create_task(_consumer(robot, gate_receipt))
        await asyncio.gather(producer, consumer)
        if not (await _is_goal_reached(robot)):
            continue
        break


async def _is_goal_reached(robot: Robot) -> bool:
    left_obs = await robot.inspect("LEFT", "left_verification")
    right_obs = await robot.inspect("RIGHT", "right_verification")
    return (
        left_obs.value.get("item_id") == "left_part"
        and left_obs.value.get("verified_by") == "LEFT"
        and right_obs.value.get("item_id") == "left_part"
        and right_obs.value.get("verified_by") == "RIGHT"
    )
