import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Task D5_FRESHNESS-SHORT-LH
    #
    # Structure: DEPENDENCY_DISTANCE=SHORT, layout=LH
    #   - Two separate work lanes (LEFT, RIGHT).
    #   - Each arm approaches its source from home, grasps its part,
    #     carries it to its target, releases, and departs.
    #   - The focal dependency: the "route" observation for left_part
    #     must be taken AFTER the right arm's release invalidates the
    #     peer placement.  h_variant.invalidates == true, so the
    #     right release bumps the version of the route fact.
    #
    # Required order (from PUBLIC TASK):
    #   1. RIGHT arm: approach right_source from right_home, grasp
    #      right_part, move to right_target, release, depart.
    #   2. LEFT arm: approach left_source from left_home, grasp
    #      left_part, move to left_target, release, depart.
    #   3. The route observation for left_part must be taken after
    #      the right release (which invalidates the peer placement).
    #
    # We implement the serial carried-path structure: the right lane
    # completes its carry and release first (invalidating the route
    # fact), then the left lane proceeds, and the route observation
    # is refreshed/inspected after the invalidation.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Phase 1: RIGHT arm — approach, grasp, carry, release, depart.
    # ------------------------------------------------------------------
    # Approach sequence for RIGHT: start at right_home, interaction
    # pose right_source, required next call is grasp, max intervening
    # logical time 0.0.  So we must move to right_source and then
    # immediately grasp right_part in the same coroutine with no
    # intervening calls.
    await robot.move("RIGHT", "right_source")
    right_grasp_obs = await robot.grasp("RIGHT", "right_part")

    # Carry right_part to right_target.
    await robot.move("RIGHT", "right_target")

    # Release right_part at right_target (a logical support).
    await robot.release("RIGHT", "right_part", "right_target")

    # Immediately begin the separating departure for the RIGHT arm.
    # The release semantics require the same coroutine to start the
    # departure immediately; we move to right_depart.
    await robot.move("RIGHT", "right_depart")

    # ------------------------------------------------------------------
    # Phase 2: LEFT arm — approach, grasp, carry, release, depart.
    # ------------------------------------------------------------------
    # Approach sequence for LEFT: start at left_home, interaction
    # pose left_source, required next call is grasp, max intervening
    # logical time 0.0.
    await robot.move("LEFT", "left_source")
    left_grasp_obs = await robot.grasp("LEFT", "left_part")

    # Carry left_part to left_target.
    await robot.move("LEFT", "left_target")

    # Release left_part at left_target.
    await robot.release("LEFT", "left_part", "left_target")

    # Immediately begin the separating departure for the LEFT arm.
    await robot.move("LEFT", "left_depart")

    # ------------------------------------------------------------------
    # Phase 3: Focal dependency — route observation after invalidation.
    #
    # The right release invalidated the peer placement (h_variant
    # invalidates == true).  The route observation for left_part must
    # occur after that invalidation.  We take a fresh observation of
    # the "route" fact now, after the right release has occurred.
    #
    # The development contract specifies:
    #   observation: {fact_id: "route", object_id: "left_part"}
    #
    # We use refresh to obtain a current, valid observation of the
    # route fact for left_part.  The observation is taken after the
    # right release, satisfying the dependency distance requirement.
    # ------------------------------------------------------------------
    route_obs = await robot.refresh("LEFT", "route")

    # Verify the observation is for the correct fact and item.
    # (Internal verification; no output.)
    assert route_obs.fact_id == "route"
    assert route_obs.version >= 1

    # ------------------------------------------------------------------
    # Terminal obligations:
    #   - both parts at their own target
    #   - both arms at departure and empty
    #
    # Both parts have been released at their targets.
    # Both arms have moved to their departure poses and are empty
    # (no hold/grasp outstanding).
    # ------------------------------------------------------------------

    # No outstanding tasks, timers, or callbacks to await.
    return None
