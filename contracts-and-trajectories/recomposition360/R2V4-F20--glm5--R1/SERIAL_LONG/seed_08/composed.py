import asyncio
async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "counterforce_state", 20)
    await robot.move("LEFT", "left_approach", 4)


async def atom_a_dependency(robot):
    await robot.move("LEFT", "support_pose", 4)
    robot.signal("counterforce_ready")
    robot.signal("torque_ready")


async def atom_a_commit(robot):
    receipt_axle = await robot.wait_event("axle_seated", 20)
    receipt_counter = await robot.wait_event("counterforce_ready", 20)
    receipt_torque = await robot.wait_event("torque_ready", 20)
    robot.clear_event("axle_seated", expected_version=receipt_axle.version)
    robot.clear_event("counterforce_ready", expected_version=receipt_counter.version)
    robot.clear_event("torque_ready", expected_version=receipt_torque.version)


async def atom_a_finish(robot):
    await robot.inspect("LEFT", "context_fact_5")
    await robot.release_resource("LEFT", "counterforce_state")
    await robot.move("LEFT", "left_home", 4)


async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)


async def atom_b_dependency(robot):
    await robot.wait_event("counterforce_ready", 20)
    await robot.wait_event("torque_ready", 20)
    await robot.move("RIGHT", "right_protected", 4)


async def atom_b_commit(robot):
    robot.signal("axle_seated")


async def atom_b_finish(robot):
    await robot.move("RIGHT", "right_home", 4)
_RQ2_SEED = 8
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
    await _rq2_checkpoint("b_prepare_before")
    await atom_b_prepare(robot)
    await _rq2_checkpoint("b_dependency_before")
    await atom_b_dependency(robot)
    await _rq2_checkpoint("b_commit_before")
    await atom_b_commit(robot)
    await _rq2_checkpoint("b_finish_before")
    await atom_b_finish(robot)
    await _rq2_checkpoint("a_commit_before")
    await atom_a_commit(robot)
    await _rq2_checkpoint("a_finish_before")
    await atom_a_finish(robot)
