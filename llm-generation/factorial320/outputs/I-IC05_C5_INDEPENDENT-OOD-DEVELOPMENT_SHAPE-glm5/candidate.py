async def run_task(robot):
    """IC05_C5_INDEPENDENT-OOD-DEVELOPMENT_SHAPE, variant A.

    Required structure: FOR -> IF -> PAR_JOIN.
    Inside one finite loop iteration, concurrently join an rq2_gate producer
    and consumer; the consumer waits the exact active receipt, executes the
    complete inherited mission, then clears that version.
    """

    # ---- FOR: one finite loop iteration ----
    for _ in range(1):
        # ---- IF: contains the join ----
        if True:
            # ---- PAR_JOIN: producer + consumer concurrently ----
            producer_task = asyncio.create_task(_produce_gate(robot))
            consumer_task = asyncio.create_task(_consume_and_mission(robot))
            await asyncio.gather(producer_task, consumer_task)

    # Final goal: rq2_gate inactive at return.
    # The consumer clears the exact receipt version it consumed, so the gate
    # is inactive here.


async def _produce_gate(robot):
    """rq2_gate producer: signal the gate active, yielding the receipt."""
    receipt = robot.signal("rq2_gate")
    return receipt


async def _consume_and_mission(robot):
    """Consumer: wait the exact active receipt, run the complete inherited
    mission (both independent attachment chains), then clear that version."""
    receipt = await robot.wait_event("rq2_gate", 5)
    await _run_inherited_mission(robot)
    robot.clear_event("rq2_gate", expected_version=receipt.version)


async def _run_inherited_mission(robot):
    """Complete inherited mission: both parts to their own target, both arms
    at departure and empty. Serial structure per required_order."""
    await _do_lane(robot, "LEFT", "left_part", "left_home", "left_source",
                   "left_target", "left_depart")
    await _do_lane(robot, "RIGHT", "right_part", "right_home", "right_source",
                  "right_target", "right_depart")


async def _do_lane(robot, arm, object_id, start_pose, source_pose,
                   target_pose, depart_pose):
    """One independent attachment chain:
    approach from start_pose -> grasp -> transport -> release -> depart."""
    await robot.move(arm, start_pose)
    await robot.move(arm, source_pose)
    await robot.grasp(arm, object_id)
    await robot.move(arm, target_pose)
    await robot.release(arm, object_id, target_pose)
    await robot.move(arm, depart_pose)


import asyncio
