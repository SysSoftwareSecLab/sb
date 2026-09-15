import asyncio
from bridge_robot_api import Robot


async def _worker_a_left(robot: Robot, alloc_obs, gate_receipt) -> None:
    """A's LEFT candidate: inspect allocation, transport shared_part if selected."""
    # Both workers independently inspect allocation once before choosing their own branch.
    left_alloc = await robot.inspect("LEFT", "allocation")

    if alloc_obs.value.get("selected_arm") != "LEFT":
        return  # unselected arm makes no move/grasp/release call

    # Only the arm named by the current controller-issued allocation may propose approach.
    # The selected grasp must carry that arm's own current allocation observation.
    await robot.move("LEFT", "shared_source", 4, receipt=gate_receipt)
    await robot.grasp("LEFT", "shared_part", observation=left_alloc)
    await robot.move("LEFT", "shared_target", 4, receipt=gate_receipt)
    await robot.release("LEFT", "shared_part", "shared_target")
    # Release at target and immediately depart (same coroutine, no intervening calls).
    await robot.move("LEFT", "left_depart", 4)
    # Goal: selected LEFT empty at left_depart.


async def _worker_a_right(robot: Robot, alloc_obs, gate_receipt) -> None:
    """A's RIGHT candidate: inspect allocation, remain at home if not selected."""
    # Both workers independently inspect allocation once before choosing their own branch.
    await robot.inspect("RIGHT", "allocation")

    if alloc_obs.value.get("selected_arm") != "RIGHT":
        return  # unselected arm makes no move/grasp/release call; remains at right_home.


async def _gap_checks(robot: Robot, gate_receipt) -> None:
    """Acquire and release rq2_gap_0/1/2 once each with LEFT, in numeric order."""
    for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", rid, 4)
        await robot.release_resource("LEFT", rid)
    # rq2_gap_0, rq2_gap_1 and rq2_gap_2 all free and OFF at return.


async def run_task(robot: Robot) -> None:
    # Read the public initial allocation observation (selected_arm = LEFT).
    alloc_obs = await robot.inspect("LEFT", "allocation")

    # Signal rq2_gate exactly once; keep active while executing the complete inherited dual-arm mission.
    gate_receipt = robot.signal("rq2_gate")

    # Joined concurrent scheduling for both the inherited dual-arm mission and the rq2_gate producer/consumer.
    # A runs candidate LEFT then RIGHT serially; B gathers them concurrently.
    # Complete all three rq2_gap resource checks, and only then wait for rq2_gate.
    await asyncio.gather(
        asyncio.gather(
            _worker_a_left(robot, alloc_obs, gate_receipt),
            _worker_a_right(robot, alloc_obs, gate_receipt),
        ),
        _gap_checks(robot, gate_receipt),
    )

    # Wait for rq2_gate's exact active receipt exactly once (after gap checks complete).
    waited_receipt = await robot.wait_event("rq2_gate", 4)

    # Clear rq2_gate exactly that version after its assigned protected scope (the mission).
    robot.clear_event("rq2_gate", expected_version=waited_receipt.version)
    # rq2_gate inactive at return.
