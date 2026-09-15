async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "board_stable_support", 20)
    await robot.move("LEFT", "left_approach", 4)

async def atom_a_dependency(robot):
    await robot.inspect("LEFT", "context_fact_2")
    await robot.move("LEFT", "support_pose", 4)
    robot.signal("support_ready")

async def atom_a_commit(robot):
    receipt_ts = await robot.wait_event("transfer_started", 20)
    receipt_sc = await robot.wait_event("stable_commit", 20)
    receipt_sr = await robot.wait_event("support_ready", 20)
    robot.clear_event("transfer_started", expected_version=receipt_ts.version)
    robot.clear_event("stable_commit", expected_version=receipt_sc.version)
    robot.clear_event("support_ready", expected_version=receipt_sr.version)

async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "board_stable_support")
    await robot.move("LEFT", "left_home", 4)

async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)

async def atom_b_dependency(robot):
    receipt_sr = await robot.wait_event("support_ready", 20)
    robot.signal("transfer_started")
    await robot.move("RIGHT", "right_protected", 4)

async def atom_b_commit(robot):
    robot.signal("stable_commit")

async def atom_b_finish(robot):
    await robot.move("RIGHT", "right_home", 4)
