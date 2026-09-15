async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "detour_corridor", 20)
    await robot.move("LEFT", "left_approach", 4)


async def atom_a_dependency(robot):
    await robot.move("LEFT", "a_zone", 4)
    robot.signal("obstruction_seen")


async def atom_a_commit(robot):
    await robot.move("LEFT", "left_exit", 4)


async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "detour_corridor")
    receipt = await robot.wait_event("obstruction_seen", 20)
    robot.clear_event("obstruction_seen", expected_version=receipt.version)
    robot.signal("corridor_released")
    await robot.move("LEFT", "left_home", 4)


async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)


async def atom_b_dependency(robot):
    receipt = await robot.wait_event("corridor_released", 20)
    robot.clear_event("corridor_released", expected_version=receipt.version)
    robot.signal("detour_ready")
    await robot.move("RIGHT", "b_zone", 4)


async def atom_b_commit(robot):
    await robot.inspect("RIGHT", "context_fact_4")
    await robot.move("RIGHT", "right_exit", 4)


async def atom_b_finish(robot):
    receipt = await robot.wait_event("corridor_released", 20)
    robot.clear_event("corridor_released", expected_version=receipt.version)
    receipt = await robot.wait_event("detour_ready", 20)
    robot.clear_event("detour_ready", expected_version=receipt.version)
    await robot.move("RIGHT", "right_home", 4)
