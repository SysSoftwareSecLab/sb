import asyncio
async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "tool_rack_approach", 20)
    await robot.move("LEFT", "left_approach", 4)

async def atom_a_dependency(robot):
    await robot.move("LEFT", "a_zone", 4)

async def atom_a_commit(robot):
    await robot.move("LEFT", "left_exit", 4)
    robot.signal("tool_returned")

async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "tool_rack_approach")
    await robot.move("LEFT", "left_home", 4)

async def atom_b_prepare(robot):
    await robot.move("RIGHT", "right_approach", 4)

async def atom_b_dependency(robot):
    await robot.inspect("RIGHT", "context_fact_3")
    receipt = await robot.wait_event("tool_returned", 20)
    await robot.acquire("RIGHT", "tool_rack_approach", 20)
    await robot.move("RIGHT", "b_zone", 4)

async def atom_b_commit(robot):
    await robot.move("RIGHT", "right_exit", 4)

async def atom_b_finish(robot):
    await robot.release_resource("RIGHT", "tool_rack_approach")
    receipt = await robot.wait_event("tool_returned", 20)
    robot.clear_event("tool_returned", expected_version=receipt.version)
    await robot.move("RIGHT", "right_home", 4)
_RQ2_SEED = 5
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
