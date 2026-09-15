from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Task: D5_FRESHNESS-LONG-LH
    # Layout LH: two lanes, LEFT and RIGHT, each with its own part.
    # The focal dependency: peer placement (RIGHT releasing right_part)
    # invalidates the first route observation (fact_id="route",
    # object_id="left_part") before refresh.
    #
    # Required structure (DEPENDENCY_DISTANCE=LONG):
    #   1. LEFT approaches left_source from left_home and grasps left_part.
    #   2. LEFT inspects "route" -> first observation (version 1).
    #   3. RIGHT approaches right_source from right_home and grasps right_part.
    #   4. RIGHT moves to right_target and releases right_part there.
    #      This release invalidates the "route" observation (h_variant
    #      invalidates=true, invalidation_on_release for right_part).
    #   5. LEFT refreshes "route" -> new observation (version 2).
    #   6. LEFT moves to left_target and releases left_part.
    #   7. Both arms move to their departure poses, empty.
    # ------------------------------------------------------------------

    # --- Step 1: LEFT approach + grasp left_part ---------------------
    # Approach must start from left_home and the very next robot call
    # must be grasp (max_intervening_logical_time_s = 0.0).
    await robot.move("LEFT", "left_home")
    await robot.grasp("LEFT", "left_part")

    # --- Step 2: LEFT inspects route (first observation) -------------
    first_route: Observation = await robot.inspect("LEFT", "route")

    # --- Step 3: RIGHT approach + grasp right_part -------------------
    await robot.move("RIGHT", "right_home")
    await robot.grasp("RIGHT", "right_part")

    # --- Step 4: RIGHT carries right_part to right_target and releases
    # The release of right_part invalidates the "route" observation.
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")

    # --- Step 5: LEFT refreshes route (new observation) --------------
    refreshed_route: Observation = await robot.refresh("LEFT", "route")

    # --- Step 6: LEFT carries left_part to left_target and releases --
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")

    # --- Step 7: both arms to departure poses, empty -----------------
    await robot.move("LEFT", "left_depart")
    await robot.move("RIGHT", "right_depart")
