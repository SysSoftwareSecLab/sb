async def atom_a_prepare(robot):
    await robot.inspect("LEFT", "context_fact_0")
    await robot.acquire("LEFT", "retry_zone", 20)
    await robot.move("LEFT", "left_approach", 4)


async def atom_a_dependency(robot):
    await robot.move("LEFT", "a_zone", 4)
    robot.signal("dependency_active")


async def atom_a_commit(robot):
    await robot.move("LEFT", "left_exit", 4)


async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "retry_zone")
    receipt = await robot.wait_event("dependency_active", 20)
    robot.clear_event("dependency_active", expected_version=receipt.version)
    robot.signal("zone_released")
    await robot.move("LEFT", "left_home", 4)


async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)


async def atom_b_dependency(robot):
    await robot.wait_event("zone_released", 20)
    await robot.move("RIGHT", "b_zone", 4)


async def atom_b_commit(robot):
    await robot.move("RIGHT", "right_exit", 4)


async def atom_b_finish(robot):
    receipt = await robot.wait_event("zone_released", 20)
    robot.clear_event("zone_released", expected_version=receipt.version)
    await robot.move("RIGHT", "right_home", 4)
