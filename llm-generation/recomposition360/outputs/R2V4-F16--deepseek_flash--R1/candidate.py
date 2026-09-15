async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "reject_route", 20)
    await robot.move("LEFT", "reject_source", 4)
    await robot.grasp("LEFT", "rejected_part")


async def atom_a_dependency(robot):
    robot.signal("reject_declared")


async def atom_a_commit(robot):
    await robot.move("LEFT", "reject_bin", 4)
    await robot.release("LEFT", "rejected_part", "reject_bin")
    robot.signal("reroute_commit")


async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "reject_route")
    await robot.move("LEFT", "left_home", 4)


async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)


async def atom_b_dependency(robot):
    await robot.inspect("RIGHT", "context_fact_3")
    await robot.wait_event("reroute_commit", 20)
    await robot.move("RIGHT", "original_route", 4)


async def atom_b_commit(robot):
    robot.signal("cleanup_done")


async def atom_b_finish(robot):
    receipt = await robot.wait_event("reject_declared", 20)
    robot.clear_event("reject_declared", expected_version=receipt.version)
    receipt = await robot.wait_event("reroute_commit", 20)
    robot.clear_event("reroute_commit", expected_version=receipt.version)
    receipt = await robot.wait_event("cleanup_done", 20)
    robot.clear_event("cleanup_done", expected_version=receipt.version)
    await robot.move("RIGHT", "right_home", 4)
