async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "cure_complete_event", 20)
    await robot.move("LEFT", "a_zone", 4)


async def atom_a_dependency(robot):
    robot.signal("clamp_ready")


async def atom_a_commit(robot):
    receipt_cure_checked = await robot.wait_event("cure_checked", 20)
    robot.clear_event("cure_checked", expected_version=receipt_cure_checked.version)
    receipt_consumer_commit = await robot.wait_event("consumer_commit", 20)
    robot.clear_event("consumer_commit", expected_version=receipt_consumer_commit.version)
    receipt_clamp_ready = await robot.wait_event("clamp_ready", 20)
    robot.clear_event("clamp_ready", expected_version=receipt_clamp_ready.version)


async def atom_a_finish(robot):
    await robot.inspect("LEFT", "context_fact_5")
    await robot.release_resource("LEFT", "cure_complete_event")
    await robot.move("LEFT", "left_home", 4)


async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)


async def atom_b_dependency(robot):
    await robot.wait_event("clamp_ready", 20)
    await robot.move("RIGHT", "right_protected", 4)


async def atom_b_commit(robot):
    robot.signal("consumer_commit")


async def atom_b_finish(robot):
    robot.signal("cure_checked")
    await robot.move("RIGHT", "right_home", 4)
