import asyncio
from bridge_robot_api import Robot


async def _left_branch(robot: Robot) -> None:
    # Inherited dual-arm mission for LEFT: verify left_part, transport to left_target, depart.
    left_ver = await robot.inspect("LEFT", "left_verification")
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part", observation=left_ver)
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")
    robot.signal("left_ready")


async def _right_branch(robot: Robot) -> None:
    # Inherited dual-arm mission for RIGHT: verify right_part, transport to right_target, depart.
    right_ver = await robot.inspect("RIGHT", "right_verification")
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part", observation=right_ver)
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
    robot.signal("right_ready")


async def _gap_checks(robot: Robot) -> None:
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order.
    for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", rid, 5)
        await robot.release_resource("LEFT", rid)


async def run_task(robot: Robot) -> None:
    # Concurrent scheduling: gap checks and both inherited verifier branches run together.
    gap_task = asyncio.create_task(_gap_checks(robot))
    left_task = asyncio.create_task(_left_branch(robot))
    right_task = asyncio.create_task(_right_branch(robot))

    # Complete all three rq2_gap resource checks before signalling rq2_gate.
    await gap_task

    # Signal rq2_gate exactly once.
    gate_receipt = robot.signal("rq2_gate")

    # Wait immediately after the signal; wait its exact active receipt exactly once.
    await robot.wait_event("rq2_gate", 5)

    # Keep rq2_gate active while executing the complete inherited dual-arm mission after the wait.
    await asyncio.gather(left_task, right_task)

    # Clear rq2_gate only after the mission, using the exact version from the receipt.
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # rq2_gate inactive at return; resources free and OFF; arms at departure and empty.
    return
