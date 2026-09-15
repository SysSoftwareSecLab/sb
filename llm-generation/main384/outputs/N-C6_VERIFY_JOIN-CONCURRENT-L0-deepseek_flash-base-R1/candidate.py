import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # Two independent verifier branches, joined before one payload consumer.
    # LEFT branch: approach left_part from left_home, grasp, verify, transport to left_target, release, depart.
    # RIGHT branch: approach right_part from right_home, grasp, verify, transport to right_target, release, depart.
    # Join: both branches signal their ready event; a consumer waits for both, then clears them.

    left_ready = robot.signal("left_ready")
    right_ready = robot.signal("right_ready")

    async def left_branch():
        # Approach must start from left_home and immediately grasp left_part.
        await robot.move("LEFT", "left_home")
        obs = await robot.grasp("LEFT", "left_part")
        # Verify left_part using the issued grasp observation.
        await robot.inspect("LEFT", "left_verification")
        await robot.move("LEFT", "left_target")
        await robot.release("LEFT", "left_part", "left_target")
        await robot.move("LEFT", "left_depart")

    async def right_branch():
        await robot.move("RIGHT", "right_home")
        obs = await robot.grasp("RIGHT", "right_part")
        await robot.inspect("RIGHT", "right_verification")
        await robot.move("RIGHT", "right_target")
        await robot.release("RIGHT", "right_part", "right_target")
        await robot.move("RIGHT", "right_depart")

    async def consumer():
        # Wait for both verifier branches to signal readiness.
        lr = await robot.wait_event("left_ready", 10)
        rr = await robot.wait_event("right_ready", 10)
        # Clear both events using their issued versions.
        robot.clear_event("left_ready", expected_version=lr.version)
        robot.clear_event("right_ready", expected_version=rr.version)

    await asyncio.gather(left_branch(), right_branch(), consumer())
