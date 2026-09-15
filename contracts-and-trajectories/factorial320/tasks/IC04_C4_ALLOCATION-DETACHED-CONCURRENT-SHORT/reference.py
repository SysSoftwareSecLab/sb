import asyncio
async def run_task(robot):
    async def _rq2_mission():
        async def worker(arm):
            allocation = await robot.inspect(arm, "allocation")
            if allocation.value["selected_arm"] == arm:
                await robot.move(arm, "shared_source")
                await robot.grasp(arm, "shared_part", observation=allocation)
                await robot.move(arm, "shared_target")
                await robot.release(arm, "shared_part", "shared_target")
                await robot.move(arm, arm.lower() + "_depart")
        await asyncio.gather(worker("LEFT"), worker("RIGHT"))
    async def _rq2_spacing():
        for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
            await robot.acquire("LEFT", resource_id, 20)
            await robot.release_resource("LEFT", resource_id)
    async def _rq2_producer():
        return robot.signal("rq2_gate")
    async def _rq2_consumer():
        receipt = await robot.wait_event("rq2_gate", 20)
        if receipt.version <= 0:
            raise RuntimeError("invalid rq2_gate receipt")
        robot.clear_event("rq2_gate", expected_version=receipt.version)
    await _rq2_spacing()
    await asyncio.gather(_rq2_producer(), _rq2_consumer())
    await _rq2_mission()
