async def run_task(robot):
    # D5_FRESHNESS-LONG-L0: two independent lanes; no resources, no events,
    # no invalidation_on_release, no state_facts. Development obligation:
    # observe route for left_part, then refresh after peer release invalidates
    # the first route observation. Since world.invalidation_on_release is
    # empty, the route fact is never invalidated by any release in this task;
    # the obligation is still implemented by issuing an initial observation
    # and a later refresh of the same closed-value fact.

    # LEFT lane: left_home -> left_source -> grasp left_part ->
    # left_target -> release left_part -> left_depart.
    await robot.move("LEFT", "left_source")
    left_obs = await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")

    # RIGHT lane: right_home -> right_source -> grasp right_part ->
    # right_target -> release right_part -> right_depart.
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")

    # Development observation obligation: inspect route for left_part, then
    # refresh route after peer placement. The route value is closed
    # (destination=left_target, item_id=left_part); refresh re-reads the same
    # fact_id.
    await robot.inspect("LEFT", "route")
    await robot.refresh("LEFT", "route")
