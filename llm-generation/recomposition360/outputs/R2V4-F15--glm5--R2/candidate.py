async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "stop_and_release_state", 20)
    await robot.move("LEFT", "a_zone", 4)

async def atom_a_dependency(robot):
    await robot.inspect("LEFT", "context_fact_2")
    robot.signal("stop_started")

async def atom_a_commit(robot):
    robot.signal("hold_ack")

async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "stop_and_release_state")
    await robot.move("LEFT", "left_home", 4)

async def atom_b_prepare(robot):
    await robot.acquire("RIGHT", "payload_hold", 20)
    await robot.move("RIGHT", "right_approach", 4)

async def atom_b_dependency(robot):
    receipt = await robot.wait_event("hold_ack", 20)
    await robot.release_resource("RIGHT", "payload_hold")
    robot.signal("payload_released")

async def atom_b_commit(robot):
    await robot.move("RIGHT", "right_exit", 4)

async def atom_b_finish(robot):
    receipt_stop_started = await robot.wait_event("stop_started", 20)
    robot.clear_event("stop_started", expected_version=receipt_stop_started.version)
    receipt_hold_ack = await robot.wait_event("hold_ack", 20)
    robot.clear_event("hold_ack", expected_version=receipt_hold_ack.version)
    receipt_payload_released = await robot.wait_event("payload_released", 20)
    robot.clear_event("payload_released", expected_version=receipt_payload_released.version)
    await robot.move("RIGHT", "right_home", 4)
