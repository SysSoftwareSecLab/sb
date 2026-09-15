async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "tension_ready_event", 20)
    await robot.move("LEFT", "a_zone", 4)

async def atom_a_dependency(robot):
    robot.signal("tension_ready")

async def atom_a_commit(robot):
    receipt = await robot.wait_event("threaded", 20)
    robot.clear_event("threaded", expected_version=receipt.version)
    receipt = await robot.wait_event("consumer_commit", 20)
    robot.clear_event("consumer_commit", expected_version=receipt.version)
    receipt = await robot.wait_event("tension_ready", 20)
    robot.clear_event("tension_ready", expected_version=receipt.version)

async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "tension_ready_event")
    await robot.move("LEFT", "left_home", 4)

async def atom_b_prepare(robot):
    await robot.inspect("RIGHT", "context_fact_1")
    await robot.move("RIGHT", "right_approach", 4)

async def atom_b_dependency(robot):
    await robot.wait_event("tension_ready", 20)
    robot.signal("threaded")
    await robot.move("RIGHT", "right_protected", 4)

async def atom_b_commit(robot):
    robot.signal("consumer_commit")

async def atom_b_finish(robot):
    await robot.move("RIGHT", "right_home", 4)
