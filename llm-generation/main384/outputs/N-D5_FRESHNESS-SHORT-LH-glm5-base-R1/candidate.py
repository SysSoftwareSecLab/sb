async def run_task(robot):
    """D5_FRESHNESS-SHORT-LH: both parts to targets, both arms depart and empty.

    Structure: DEPENDENCY_DISTANCE=SHORT, layout=LH (serial carried paths cross
    in XY projection).  Each arm approaches its own part from home, grasps,
    carries to its target, releases, and immediately departs.  The route
    observation for left_part is inspected after the right arm's invalidating
    peer placement is complete, preserving the closed-value observation versus
    invalidation.
    """

    # --- LEFT arm: left_part left_source -> left_target -> left_depart ---
    await robot.move("LEFT", "left_source")
    left_obs = await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")

    # --- RIGHT arm: right_part right_source -> right_target -> right_depart ---
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")

    # --- Atomic route observation for left_part after peer placement ---
    await robot.inspect("LEFT", "route")
