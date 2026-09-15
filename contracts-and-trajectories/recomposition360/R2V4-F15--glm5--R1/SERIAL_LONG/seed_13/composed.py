import asyncio
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
_RQ2_SEED = 13
async def _rq2_checkpoint(label):
    label_code = sum((index + 1) * ord(character) for index, character in enumerate(label))
    turns = ((_RQ2_SEED >> (label_code % 4)) ^ (_RQ2_SEED * ((label_code % 7) + 1)) ^ label_code) % 4
    for _ in range(turns):
        await asyncio.sleep(0)
async def _rq2_neutral_gap(robot):
    await robot.inspect("LEFT", "neutral_fact_0")
    await _rq2_checkpoint("neutral_0")
    await robot.inspect("LEFT", "neutral_fact_1")
    await _rq2_checkpoint("neutral_1")
    await robot.inspect("LEFT", "neutral_fact_2")
    await _rq2_checkpoint("neutral_2")
async def run_task(robot):
    await _rq2_checkpoint("a_prepare_before")
    await atom_a_prepare(robot)
    await _rq2_checkpoint("a_dependency_before")
    await atom_a_dependency(robot)
    await _rq2_neutral_gap(robot)
    await _rq2_checkpoint("a_commit_before")
    await atom_a_commit(robot)
    await _rq2_checkpoint("a_finish_before")
    await atom_a_finish(robot)
    await _rq2_checkpoint("b_prepare_before")
    await atom_b_prepare(robot)
    await _rq2_checkpoint("b_dependency_before")
    await atom_b_dependency(robot)
    await _rq2_checkpoint("b_commit_before")
    await atom_b_commit(robot)
    await _rq2_checkpoint("b_finish_before")
    await atom_b_finish(robot)
