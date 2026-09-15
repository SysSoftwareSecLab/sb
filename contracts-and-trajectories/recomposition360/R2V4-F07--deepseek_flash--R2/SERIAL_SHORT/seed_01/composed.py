import asyncio
async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "board_stable_support", 20)
    await robot.move("LEFT", "left_approach", 4)


async def atom_a_dependency(robot):
    await robot.inspect("LEFT", "context_fact_2")
    await robot.move("LEFT", "support_pose", 4)
    robot.signal("support_ready")


async def atom_a_commit(robot):
    transfer_started_receipt = await robot.wait_event("transfer_started", 20)
    stable_commit_receipt = await robot.wait_event("stable_commit", 20)
    support_ready_receipt = await robot.wait_event("support_ready", 20)
    robot.clear_event("transfer_started", expected_version=transfer_started_receipt.version)
    robot.clear_event("stable_commit", expected_version=stable_commit_receipt.version)
    robot.clear_event("support_ready", expected_version=support_ready_receipt.version)


async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "board_stable_support")
    await robot.move("LEFT", "left_home", 4)


async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)


async def atom_b_dependency(robot):
    await robot.wait_event("support_ready", 20)
    robot.signal("transfer_started")
    await robot.move("RIGHT", "right_protected", 4)


async def atom_b_commit(robot):
    robot.signal("stable_commit")


async def atom_b_finish(robot):
    await robot.move("RIGHT", "right_home", 4)
_RQ2_SEED = 1
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
    await _rq2_neutral_gap(robot)
    await _rq2_checkpoint("a_dependency_before")
    await atom_a_dependency(robot)
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
