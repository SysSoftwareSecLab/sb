async def run_task(robot):
    """C2_DUAL_RESOURCE-SERIAL-LH, variant A.

    Serial execution of two complete workers. Each worker:
      - acquires fixture then tool (try/finally releases on timeout),
      - carries the corresponding part to target while owning both,
      - releases part at target and departs,
      - releases tool then fixture (both OFF and unowned).
    """

    async def worker(arm, part, start_pose, source, target, depart):
        acquired = []
        try:
            # Acquire fixture then tool, same order for both workers.
            await robot.acquire(arm, "fixture", 5)
            acquired.append("fixture")
            await robot.acquire(arm, "tool", 5)
            acquired.append("tool")

            # Approach from declared start_pose to interaction_pose, then
            # immediately grasp in the same virtual moment.
            await robot.move(arm, source)
            await robot.grasp(arm, part)

            # Carry part to target while owning both controllers.
            await robot.move(arm, target)

            # Release part at target (current pose == support_zone), then
            # immediately begin separating departure.
            await robot.release(arm, part, target)
            await robot.move(arm, depart)
        finally:
            # Release every successfully acquired controller, tool first
            # then fixture, ensuring OFF and unowned.
            for rid in reversed(acquired):
                try:
                    await robot.release_resource(arm, rid)
                except Exception:
                    pass

    # Variant A: run the two complete workers serially.
    await worker("LEFT", "left_part", "left_home", "left_source",
                 "left_target", "left_depart")
    await worker("RIGHT", "right_part", "right_home", "right_source",
                 "right_target", "right_depart")
