async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "suspended_load_barrier", 20)
    await robot.move("LEFT", "left_approach", 4)


async def atom_a_dependency(robot):
    await robot.move("LEFT", "barrier_pose", 4)
    robot.signal("barrier_deployed")


async def atom_a_commit(robot):
    lower_receipt = await robot.wait_event("lower_zone_clear", 20)
    barrier_receipt = await robot.wait_event("barrier_deployed", 20)
    robot.clear_event("lower_zone_clear", expected_version=lower_receipt.version)
    robot.clear_event("barrier_deployed", expected_version=barrier_receipt.version)


async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "suspended_load_barrier")
    await robot.move("LEFT", "left_home", 4)


async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)


async def atom_b_dependency(robot):
    await robot.wait_event("barrier_deployed", 20)
    await robot.move("RIGHT", "b_zone", 4)


async def atom_b_commit(robot):
    await robot.inspect("RIGHT", "context_fact_4")
    robot.signal("lower_zone_clear")


async def atom_b_finish(robot):
    await robot.move("RIGHT", "right_home", 4)
