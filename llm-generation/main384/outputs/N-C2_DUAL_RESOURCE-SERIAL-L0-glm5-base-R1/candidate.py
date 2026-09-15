async def run_task(robot):
    """C2_DUAL_RESOURCE-SERIAL-L0, variant A.

    Serial structure: run LEFT worker to completion, then RIGHT worker.
    Each worker: acquire fixture then tool, move to source, grasp part,
    move to target, release part, move to depart, release tool then fixture.
    try/finally releases any successfully acquired controllers on timeout.
    """

    fixture = "fixture"
    tool = "tool"

    async def worker(arm, start, source, target, depart, part):
        acquired_fixture = False
        acquired_tool = False
        try:
            await robot.acquire(arm, fixture, 120)
            acquired_fixture = True
            await robot.acquire(arm, tool, 120)
            acquired_tool = True

            await robot.move(arm, source)
            await robot.grasp(arm, part)

            await robot.move(arm, target)
            await robot.release(arm, part, target)

            await robot.move(arm, depart)

            await robot.release_resource(arm, tool)
            acquired_tool = False
            await robot.release_resource(arm, fixture)
            acquired_fixture = False
        finally:
            if acquired_tool:
                await robot.release_resource(arm, tool)
            if acquired_fixture:
                await robot.release_resource(arm, fixture)

    await worker(
        "LEFT",
        "left_home",
        "left_source",
        "left_target",
        "left_depart",
        "left_part",
    )
    await worker(
        "RIGHT",
        "right_home",
        "right_source",
        "right_target",
        "right_depart",
        "right_part",
    )
