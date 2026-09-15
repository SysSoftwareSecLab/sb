import asyncio
async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "latch_verified_event", 20)
    await robot.move("LEFT", "a_zone", 4)

async def atom_a_dependency(robot):
    await robot.inspect("LEFT", "context_fact_2")
    robot.signal("compression_ready")

async def atom_a_commit(robot):
    receipt = await robot.wait_event("latch_checked", 20)
    robot.clear_event("latch_checked", expected_version=receipt.version)
    receipt = await robot.wait_event("consumer_commit", 20)
    robot.clear_event("consumer_commit", expected_version=receipt.version)
    receipt = await robot.wait_event("compression_ready", 20)
    robot.clear_event("compression_ready", expected_version=receipt.version)

async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "latch_verified_event")
    await robot.move("LEFT", "left_home", 4)

async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)

async def atom_b_dependency(robot):
    await robot.wait_event("compression_ready", 20)
    await robot.move("RIGHT", "right_protected", 4)

async def atom_b_commit(robot):
    robot.signal("latch_checked")
    robot.signal("consumer_commit")

async def atom_b_finish(robot):
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
_rq2_ready = None
async def _rq2_chain_a(robot):
    await _rq2_checkpoint("a_prepare_before")
    await atom_a_prepare(robot)
    await _rq2_checkpoint("a_dependency_before")
    await atom_a_dependency(robot)
    await _rq2_neutral_gap(robot)
    _rq2_ready.set()
    await _rq2_checkpoint("a_commit_before")
    await atom_a_commit(robot)
    await _rq2_checkpoint("a_finish_before")
    await atom_a_finish(robot)
async def _rq2_chain_b(robot):
    await _rq2_checkpoint("b_prepare_before")
    await atom_b_prepare(robot)
    await _rq2_ready.wait()
    await _rq2_checkpoint("b_dependency_before")
    await atom_b_dependency(robot)
    await _rq2_checkpoint("b_commit_before")
    await atom_b_commit(robot)
    await _rq2_checkpoint("b_finish_before")
    await atom_b_finish(robot)
async def run_task(robot):
    global _rq2_ready
    _rq2_ready = asyncio.Event()
    await asyncio.gather(_rq2_chain_a(robot), _rq2_chain_b(robot))
