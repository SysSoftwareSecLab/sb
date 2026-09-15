async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "box_clear_barrier", 20)
    await robot.move("LEFT", "left_approach", 4)


async def atom_a_dependency(robot):
    await robot.move("LEFT", "left_exit", 4)
    robot.signal("aperture_clear")


async def atom_a_commit(robot):
    receipt_lid_closed = await robot.wait_event("lid_closed", 20)
    receipt_aperture_clear = await robot.wait_event("aperture_clear", 20)
    robot.clear_event("lid_closed", expected_version=receipt_lid_closed.version)
    robot.clear_event("aperture_clear", expected_version=receipt_aperture_clear.version)


async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "box_clear_barrier")
    await robot.move("LEFT", "left_home", 4)


async def atom_b_prepare(robot):
    await robot.inspect("RIGHT", "context_fact_1")
    await robot.move("RIGHT", "right_approach", 4)


async def atom_b_dependency(robot):
    receipt_aperture_clear = await robot.wait_event("aperture_clear", 20)
    await robot.move("RIGHT", "right_protected", 4)


async def atom_b_commit(robot):
    robot.signal("lid_closed")


async def atom_b_finish(robot):
    await robot.move("RIGHT", "right_home", 4)
