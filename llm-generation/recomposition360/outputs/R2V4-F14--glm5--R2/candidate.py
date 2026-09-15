async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "quarantine_zone", 20)
    await robot.move("LEFT", "a_zone", 4)


async def atom_a_dependency(robot):
    robot.signal("quarantine_ready")


async def atom_a_commit(robot):
    robot.signal("quarantine_commit")


async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "quarantine_zone")
    await robot.move("LEFT", "left_home", 4)


async def atom_b_prepare(robot):
    await robot.inspect("RIGHT", "context_fact_1")
    await robot.move("RIGHT", "replacement_source", 4)


async def atom_b_dependency(robot):
    receipt = await robot.wait_event("quarantine_commit", 20)
    await robot.grasp("RIGHT", "replacement_part")
    await robot.move("RIGHT", "recovered_bin", 4)
    await robot.release("RIGHT", "replacement_part", "recovered_bin")


async def atom_b_commit(robot):
    robot.signal("recovery_done")


async def atom_b_finish(robot):
    receipt_qr = await robot.wait_event("quarantine_ready", 20)
    robot.clear_event("quarantine_ready", expected_version=receipt_qr.version)
    receipt_qc = await robot.wait_event("quarantine_commit", 20)
    robot.clear_event("quarantine_commit", expected_version=receipt_qc.version)
    receipt_rd = await robot.wait_event("recovery_done", 20)
    robot.clear_event("recovery_done", expected_version=receipt_rd.version)
    await robot.move("RIGHT", "right_home", 4)
