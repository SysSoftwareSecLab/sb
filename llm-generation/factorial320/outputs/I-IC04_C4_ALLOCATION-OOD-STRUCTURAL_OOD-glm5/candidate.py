import asyncio
import json

from bridge_robot_api import Robot


async def _inspect_allocation(robot: Robot, arm: str) -> str:
    """Inspect the allocation fact once and return the selected arm."""
    obs = await robot.inspect(arm, "allocation")
    value = json.loads(obs.value_json)
    return value["selected_arm"]


async def _selected_transport(robot: Robot, arm: str, home_pose: str,
                              depart_pose: str) -> None:
    """Execute the complete inherited mission for the selected arm.

    Sequence: approach shared_source -> grasp shared_part (carrying own
    current allocation observation) -> move to shared_target -> release ->
    immediately depart to goal pose.
    """
    # Re-inspect allocation immediately before grasp so the carried
    # observation is current and item_id matches.
    alloc_obs = await robot.inspect(arm, "allocation")

    # Approach: start_pose must be the arm's home; immediately grasp.
    await robot.move(arm, "shared_source")
    await robot.grasp(arm, "shared_part", observation=alloc_obs)

    # Carry transport to target.
    await robot.move(arm, "shared_target")

    # Release at target support zone, then immediately depart.
    await robot.release(arm, "shared_part", "shared_target")
    await robot.move(arm, depart_pose)


async def _unselected_stay(robot: Robot, arm: str, home_pose: str) -> None:
    """Unselected arm makes no move/grasp/release call; stays at home."""
    # Inspect allocation once (already done by caller). No further action.
    return


async def _candidate(robot: Robot, arm: str, selected_arm: str) -> None:
    """One worker candidate: inspect allocation once, then branch."""
    home_pose = "left_home" if arm == "LEFT" else "right_home"
    depart_pose = "left_depart" if arm == "LEFT" else "right_depart"

    if arm == selected_arm:
        await _selected_transport(robot, arm, home_pose, depart_pose)
    else:
        await _unselected_stay(robot, arm, home_pose)


async def _consumer_mission(robot: Robot, receipt) -> None:
    """Consumer waits the exact active receipt, executes the complete
    inherited mission, then clears that version."""
    # Wait for the exact active receipt (rq2_gate).
    waited = await robot.wait_event("rq2_gate", 10)

    # Execute the complete inherited mission: inspect allocation by both
    # candidates, then selected transport.
    left_alloc = await _inspect_allocation(robot, "LEFT")
    right_alloc = await _inspect_allocation(robot, "RIGHT")

    # Both inspections must agree on the selected arm.
    assert left_alloc == right_alloc, "allocation mismatch between arms"
    selected_arm = left_alloc

    # Run candidates serially: LEFT then RIGHT (variant A, SERIAL).
    await _candidate(robot, "LEFT", selected_arm)
    await _candidate(robot, "RIGHT", selected_arm)

    # Clear the exact active receipt version after the mission completes.
    robot.clear_event("rq2_gate", expected_version=waited.version)


async def run_task(robot: Robot) -> None:
    """Entry point implementing the structural-OOD shape:
    FOR -> PAR_JOIN -> consumer IF, inside one finite loop iteration.

    The loop directly contains the join (asyncio.gather of producer and
    consumer). The consumer IF guards the complete mission.
    """
    # --- FOR: one finite loop iteration ---
    for _ in range(1):
        # --- PAR_JOIN: concurrently join rq2_gate producer and consumer ---
        async def _producer():
            """Signal rq2_gate, making it active with a new version."""
            return robot.signal("rq2_gate", item_id="shared_part")

        async def _consumer():
            # --- consumer IF guards the complete mission ---
            if True:
                await _consumer_mission(robot)

        await asyncio.gather(_producer(), _consumer())

    # At return: rq2_gate inactive (cleared by consumer),
    # shared_part at shared_target, LEFT at left_depart, RIGHT at right_home.
    return
