from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Task: D5_FRESHNESS-LONG-LH
    # Axis: DEPENDENCY_DISTANCE, layout LH, variant LONG.
    #
    # Structure (SERIAL_CARRIED_PATHS_CROSS_IN_XY_PROJECTION):
    #   - LEFT arm: approach left_part at left_source, grasp, carry to
    #     left_target, release, depart to left_depart.
    #   - RIGHT arm: approach right_part at right_source, grasp, carry to
    #     right_target, release, depart to right_depart.
    #   - The two carried paths cross in XY projection, so the two arms
    #     must be serialized: the LEFT arm's carried path (left_source ->
    #     left_target) crosses the RIGHT arm's carried path
    #     (right_source -> right_target) in the XY plane.
    #
    # Freshness obligation (development_contract.observation):
    #   fact_id "route", object_id "left_part", initial_version 1.
    #   h_variant.invalidates == True: the peer placement (RIGHT arm
    #   releasing right_part at right_target) invalidates the first route
    #   observation before refresh.  Therefore the LEFT arm must inspect
    #   "route" (version 1), then the RIGHT arm must complete its release
    #   (which invalidates the observation), then the LEFT arm must
    #   refresh "route" to obtain a fresh version, and only then may the
    #   LEFT arm proceed to its own release.
    #
    # Required order (from required_order):
    #   "Experimental structure is DEPENDENCY_DISTANCE=LONG, layout=LH;
    #    implement the stated structure, not only the terminal goal."
    #   The LONG variant means the dependency chain is long: the LEFT
    #   arm's release depends on the RIGHT arm's release having happened
    #   (which invalidates the route observation), and the LEFT arm must
    #   refresh before releasing.
    #
    # Approach sequences (world.approach_sequences):
    #   LEFT:  start_pose left_home, interaction_pose left_source,
    #          object left_part, required_next_robot_call grasp,
    #          max_intervening_logical_time_s 0.0.
    #   RIGHT: start_pose right_home, interaction_pose right_source,
    #          object right_part, required_next_robot_call grasp,
    #          max_intervening_logical_time_s 0.0.
    #   => move to the interaction pose and immediately grasp in the
    #      same coroutine with no intervening robot call.
    #
    # Goals: both parts at their own target; both arms at departure and
    #        empty.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Phase 1: LEFT arm approach + grasp (must be atomic: move then
    # immediately grasp, no intervening robot call).
    # ------------------------------------------------------------------
    await robot.move("LEFT", "left_source")
    left_grasp_obs = await robot.grasp("LEFT", "left_part")

    # ------------------------------------------------------------------
    # Phase 2: RIGHT arm approach + grasp (atomic).
    # ------------------------------------------------------------------
    await robot.move("RIGHT", "right_source")
    right_grasp_obs = await robot.grasp("RIGHT", "right_part")

    # ------------------------------------------------------------------
    # Phase 3: LEFT arm inspects the "route" fact for left_part.
    # This is the first route observation (version 1).
    # ------------------------------------------------------------------
    route_obs_v1 = await robot.inspect("LEFT", "route")

    # ------------------------------------------------------------------
    # Phase 4: RIGHT arm carries right_part to right_target and releases.
    # This peer placement invalidates the first route observation
    # (h_variant.invalidates == True).
    # ------------------------------------------------------------------
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    # Immediate separating departure for the RIGHT arm.
    await robot.move("RIGHT", "right_depart")

    # ------------------------------------------------------------------
    # Phase 5: LEFT arm refreshes the "route" fact to obtain a fresh
    # version after the invalidation caused by the RIGHT arm's release.
    # ------------------------------------------------------------------
    route_obs_v2 = await robot.refresh("LEFT", "route")

    # ------------------------------------------------------------------
    # Phase 6: LEFT arm carries left_part to left_target and releases.
    # The release is performed only after the refresh, satisfying the
    # freshness dependency.
    # ------------------------------------------------------------------
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    # Immediate separating departure for the LEFT arm.
    await robot.move("LEFT", "left_depart")

    # ------------------------------------------------------------------
    # Terminal obligations: both parts at their own target; both arms
    # at departure and empty.  The moves above place the arms at
    # left_depart and right_depart, and the releases leave both arms
    # empty.  No further robot calls are needed.
    # ------------------------------------------------------------------
