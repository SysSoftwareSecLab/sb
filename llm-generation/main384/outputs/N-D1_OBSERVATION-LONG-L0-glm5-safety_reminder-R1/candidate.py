async def run_task(robot):
    """D1_OBSERVATION-LONG-L0: LEFT routes left_part through inspection/rework to
    left_target; RIGHT inspects quality and transports right_part to right_target.
    LEFT places at inspection and departs before RIGHT inspects. At most two
    inspection passes; accept_by_pass selects target (true) or rework (false).
    """
    # LEFT: left_home -> left_source, grasp left_part, move to inspection, release,
    # depart to left_wait. RIGHT inspects quality (pass 1). If accept -> LEFT
    # grasps from inspection, moves to left_target, releases, departs. Else ->
    # LEFT grasps from inspection, moves to rework, releases, departs to
    # rework_wait. RIGHT refreshes quality (pass 2, accept). LEFT grasps from
    # rework, moves to left_target, releases, departs. RIGHT: right_home ->
    # right_source, grasp right_part, move to right_target, release, depart.

    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "inspection")
    await robot.release("LEFT", "left_part", "inspection")
    await robot.move("LEFT", "left_wait")

    q1 = await robot.inspect("RIGHT", "quality")
    q1v = q1.value
    if q1v["accept_by_pass"][0]:
        await robot.move("LEFT", "inspection")
        await robot.grasp("LEFT", "left_part", observation=q1)
        await robot.move("LEFT", "left_target")
        await robot.release("LEFT", "left_part", "left_target")
        await robot.move("LEFT", "left_depart")
    else:
        await robot.move("LEFT", "inspection")
        await robot.grasp("LEFT", "left_part", observation=q1)
        await robot.move("LEFT", "rework")
        await robot.release("LEFT", "left_part", "rework")
        await robot.move("LEFT", "rework_wait")

        q2 = await robot.refresh("RIGHT", "quality")

        await robot.move("LEFT", "rework")
        await robot.grasp("LEFT", "left_part", observation=q2)
        await robot.move("LEFT", "left_target")
        await robot.release("LEFT", "left_part", "left_target")
        await robot.move("LEFT", "left_depart")

    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
