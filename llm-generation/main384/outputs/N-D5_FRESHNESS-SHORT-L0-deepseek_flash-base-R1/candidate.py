from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Task: D5_FRESHNESS-SHORT-L0
    # Axis: DEPENDENCY_DISTANCE (SHORT)
    # Focal dependency: route observation occurs after invalidating peer placement.
    #
    # h_variant.invalidates == true, so a release that invalidates the
    # "route" observation fact must happen BEFORE we consume the route
    # observation for the LEFT part.  The development contract requires
    # the route observation (fact_id="route", object_id="left_part") to
    # be taken AFTER the invalidating peer placement (the RIGHT part
    # being placed at its target).
    #
    # Plan:
    #   1. LEFT arm: approach left_source from left_home, grasp left_part.
    #   2. RIGHT arm: approach right_source from right_home, grasp right_part.
    #   3. RIGHT arm: move to right_target, release right_part there.
    #      This is the invalidating peer placement.
    #   4. LEFT arm: inspect/refresh the "route" fact for left_part
    #      (fresh observation after invalidation).
    #   5. LEFT arm: move to left_target, release left_part there.
    #   6. Both arms: move to their departure poses, empty.
    # ------------------------------------------------------------------

    # --- Step 1: LEFT approach + grasp ---------------------------------
    # Approach sequence: start_pose left_home -> interaction_pose left_source,
    # required next robot call is grasp, max intervening logical time 0.0.
    await robot.move("LEFT", "left_source")
    left_grasp_obs = await robot.grasp("LEFT", "left_part")

    # --- Step 2: RIGHT approach + grasp --------------------------------
    await robot.move("RIGHT", "right_source")
    right_grasp_obs = await robot.grasp("RIGHT", "right_part")

    # --- Step 3: RIGHT places right_part at right_target (invalidator) -
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")

    # --- Step 4: LEFT observes route AFTER invalidation ----------------
    # The development contract requires the route observation for
    # left_part.  We refresh it so the version is current after the
    # invalidating peer placement.
    route_obs = await robot.refresh("LEFT", "route")

    # --- Step 5: LEFT places left_part at left_target ------------------
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")

    # --- Step 6: both arms to departure, empty -------------------------
    await robot.move("LEFT", "left_depart")
    await robot.move("RIGHT", "right_depart")
