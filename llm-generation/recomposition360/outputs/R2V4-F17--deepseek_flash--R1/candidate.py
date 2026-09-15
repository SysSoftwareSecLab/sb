async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "guarded_laser_cell", 20)
    await robot.move("LEFT", "left_approach", 4)


async def atom_a_dependency(robot):
    await robot.move("LEFT", "a_zone", 4)


async def atom_a_commit(robot):
    await robot.move("LEFT", "left_exit", 4)
    robot.signal("laser_off")


async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "guarded_laser_cell")
    robot.signal("guard_clear")
    await robot.move("LEFT", "left_home", 4)


async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)


async def atom_b_dependency(robot):
    await robot.wait_event("laser_off", 20)
    await robot.wait_event("guard_clear", 20)
    await robot.acquire("RIGHT", "guarded_laser_cell", 20)
    await robot.move("RIGHT", "b_zone", 4)


async def atom_b_commit(robot):
    await robot.inspect("RIGHT", "context_fact_4")
    await robot.move("RIGHT", "right_exit", 4)


async def atom_b_finish(robot):
    await robot.release_resource("RIGHT", "guarded_laser_cell")
    receipt_laser_off = await robot.wait_event("laser_off", 20)
    robot.clear_event("laser_off", expected_version=receipt_laser_off.version)
    receipt_guard_clear = await robot.wait_event("guard_clear", 20)
    robot.clear_event("guard_clear", expected_version=receipt_guard_clear.version)
    await robot.move("RIGHT", "right_home", 4)
