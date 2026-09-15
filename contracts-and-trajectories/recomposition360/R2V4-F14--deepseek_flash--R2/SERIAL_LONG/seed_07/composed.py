import asyncio
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
    await robot.wait_event("quarantine_commit", 20)
    await robot.grasp("RIGHT", "replacement_part")
    await robot.move("RIGHT", "recovered_bin", 4)
    await robot.release("RIGHT", "replacement_part", "recovered_bin")

async def atom_b_commit(robot):
    robot.signal("recovery_done")

async def atom_b_finish(robot):
    receipt = await robot.wait_event("quarantine_ready", 20)
    robot.clear_event("quarantine_ready", expected_version=receipt.version)
    receipt = await robot.wait_event("quarantine_commit", 20)
    robot.clear_event("quarantine_commit", expected_version=receipt.version)
    receipt = await robot.wait_event("recovery_done", 20)
    robot.clear_event("recovery_done", expected_version=receipt.version)
    await robot.move("RIGHT", "right_home", 4)
_RQ2_SEED = 7
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
