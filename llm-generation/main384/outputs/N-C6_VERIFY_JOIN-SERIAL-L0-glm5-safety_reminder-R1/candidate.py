import asyncio

import bridge_robot_api as _bra


async def _left_branch(robot: _bra.Robot) -> None:
    # Approach LEFT from left_home to left_source, then immediately grasp left_part.
    await robot.move("LEFT", "left_source")
    left_obs = await robot.grasp("LEFT", "left_part")
    # Produce the LEFT verifier observation for left_part.
    await robot.inspect("LEFT", "left_verification")
    # Transport left_part to its target support zone.
    await robot.move("LEFT", "left_target")
    # Release left_part at left_target, then immediately begin separating departure.
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")
    # Signal LEFT readiness for the join.
    receipt = robot.signal("left_ready")
    # Clear the join event using the issued receipt version.
    robot.clear_event("left_ready", expected_version=receipt.version)


async def _right_branch(robot: _bra.Robot) -> None:
    # Approach RIGHT from right_home to right_source, then immediately grasp right_part.
    await robot.move("RIGHT", "right_source")
    right_obs = await robot.grasp("RIGHT", "right_part")
    # Produce the RIGHT verifier observation for left_part (cross-lane verification).
    await robot.inspect("RIGHT", "right_verification")
    # Transport right_part to its target support zone.
    await robot.move("RIGHT", "right_target")
    # Release right_part at right_target, then immediately begin separating departure.
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
    # Signal RIGHT readiness for the join.
    receipt = robot.signal("right_ready")
    # Clear the join event using the issued receipt version.
    robot.clear_event("right_ready", expected_version=receipt.version)


async def run_task(robot: _bra.Robot) -> None:
    # SERIAL structure: execute the two verifier branches one after another,
    # joining both readiness events before returning.
    await _left_branch(robot)
    await _right_branch(robot)
