import asyncio

from bridge_robot_api import Robot


async def _left_worker(robot: Robot) -> None:
    # Approach LEFT gripper to left_part from left_home, then immediately grasp.
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")

    # Verify left_part with LEFT, then signal readiness for the join.
    await robot.inspect("LEFT", "left_verification")
    robot.signal("left_ready")

    # Wait for the RIGHT branch to complete its verification and join.
    await robot.wait_event("right_ready", 30)

    # Transport left_part to its target and release on the support zone.
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")

    # Immediately depart to the LEFT departure pose, leaving the part behind.
    await robot.move("LEFT", "left_depart")


async def _right_worker(robot: Robot) -> None:
    # Approach RIGHT gripper to right_part from right_home, then immediately grasp.
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")

    # Verify left_part with RIGHT, then signal readiness for the join.
    await robot.inspect("RIGHT", "right_verification")
    robot.signal("right_ready")

    # Wait for the LEFT branch to complete its verification and join.
    await robot.wait_event("left_ready", 30)

    # Transport right_part to its target and release on the support zone.
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")

    # Immediately depart to the RIGHT departure pose, leaving the part behind.
    await robot.move("RIGHT", "right_depart")


async def run_task(robot: Robot) -> None:
    """Execute the C6_VERIFY_JOIN SERIAL-LH task.

    Two independent verifier branches each approach, grasp, and inspect their
    declared part, then join via left_ready/right_ready before transporting the
    parts to their targets, releasing, and departing empty.
    """
    await asyncio.gather(_left_worker(robot), _right_worker(robot))
