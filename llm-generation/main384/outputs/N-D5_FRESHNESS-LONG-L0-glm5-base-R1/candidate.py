import asyncio
from bridge_robot_api import Robot


async def _left_lane(robot: Robot) -> None:
    # Approach from left_home to left_source, then immediately grasp left_part.
    await robot.move("LEFT", "left_source")
    left_obs = await robot.grasp("LEFT", "left_part")

    # Transport left_part to its target support zone and release there.
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")

    # Immediate separating departure after release.
    await robot.move("LEFT", "left_depart")

    # Development obligation: inspect the route observation for left_part.
    await robot.inspect("LEFT", "route")

    # Keep the issued grasp observation referenced until the lane is complete.
    _ = left_obs


async def _right_lane(robot: Robot) -> None:
    # Approach from right_home to right_source, then immediately grasp right_part.
    await robot.move("RIGHT", "right_source")
    right_obs = await robot.grasp("RIGHT", "right_part")

    # Transport right_part to its target support zone and release there.
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")

    # Immediate separating departure after release.
    await robot.move("RIGHT", "right_depart")

    # Keep the issued grasp observation referenced until the lane is complete.
    _ = right_obs


async def run_task(robot: Robot) -> None:
    # Two separate work lanes; run them concurrently as independent candidates.
    await asyncio.gather(_left_lane(robot), _right_lane(robot))
