import asyncio
async def run_task(robot):
    async def _rq2_mission():
        async def worker(arm):
            side = arm.lower()
            await robot.move(arm, side + "_source")
            await robot.grasp(arm, side + "_part")
            await robot.acquire(arm, "fixture", 20)
            tool_owned = False
            try:
                await robot.acquire(arm, "tool", 20)
                tool_owned = True
                await robot.move(arm, side + "_target")
                await robot.release(arm, side + "_part", side + "_target")
                await robot.move(arm, side + "_depart")
            finally:
                if tool_owned:
                    await robot.release_resource(arm, "tool")
                await robot.release_resource(arm, "fixture")
        await worker("LEFT")
        await worker("RIGHT")
    async def _rq2_producer():
        return robot.signal("rq2_gate")
    async def _rq2_consumer():
        receipt = await robot.wait_event("rq2_gate", 20)
        if receipt.version > 0:
            await _rq2_mission()
        robot.clear_event("rq2_gate", expected_version=receipt.version)
    for _round in range(1):
        await asyncio.gather(_rq2_producer(), _rq2_consumer())
