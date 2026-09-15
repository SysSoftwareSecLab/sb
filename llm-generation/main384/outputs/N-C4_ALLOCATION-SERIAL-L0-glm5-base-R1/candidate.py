import asyncio
from bridge_robot_api import Robot


async def _worker(robot: Robot, arm: str, allocation_obs) -> None:
    """One symmetric worker candidate.

    Both workers independently inspect allocation once before choosing their
    branch.  Only the arm named by the current controller-issued allocation may
    approach/grasp/transport; the unselected arm makes no move/grasp/release
    call and remains at home.
    """
    selected_arm = allocation_obs.value.get("selected_arm", "LEFT")
    if arm != selected_arm:
        # Unselected: remain at home, make no move/grasp/release call.
        return

    # Selected worker: approach from this arm's home, immediately grasp,
    # carry own current allocation observation, transport to shared_target,
    # release there, and immediately depart.
    if arm == "LEFT":
        start_pose = "left_home"
        depart_pose = "left_depart"
    else:
        start_pose = "right_home"
        depart_pose = "right_depart"

    # Approach: move to shared_source, then immediately grasp in same virtual
    # moment (no intervening inspect/wait/other call/coroutine switch).
    await robot.move(arm, start_pose)
    await robot.move(arm, "shared_source")
    await robot.grasp(arm, "shared_part", observation=allocation_obs)

    # Transport carried object to target.
    await robot.move(arm, "shared_target")

    # Release at target (current pose == shared_target, a logical support),
    # then immediately begin separation in the same coroutine.
    await robot.release(arm, "shared_part", "shared_target")
    await robot.move(arm, depart_pose)


async def run_task(robot: Robot) -> None:
    """C4_ALLOCATION-SERIAL-L0, variant A.

    Structure A: run candidate LEFT then RIGHT serially.  Both perform the
    same inspections and one selected transport.  Allocation selects LEFT
    initially, so LEFT transports shared_part to shared_target and departs to
    left_depart; RIGHT remains at right_home.
    """
    # Both workers independently inspect allocation once before choosing.
    left_alloc = await robot.inspect("LEFT", "allocation")
    right_alloc = await robot.inspect("RIGHT", "allocation")

    # Candidate LEFT then RIGHT serially (SERIAL structure A).
    await _worker(robot, "LEFT", left_alloc)
    await _worker(robot, "RIGHT", right_alloc)
