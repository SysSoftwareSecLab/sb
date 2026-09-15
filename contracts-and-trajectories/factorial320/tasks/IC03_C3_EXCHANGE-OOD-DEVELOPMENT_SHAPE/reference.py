import asyncio
async def run_task(robot):
    async def _rq2_mission():
        async def deposit(arm):
            side = arm.lower()
            await robot.move(arm, side + "_source")
            await robot.grasp(arm, side + "_part")
            await robot.move(arm, side + "_pad")
            await robot.release(arm, side + "_part", side + "_pad")
            await robot.move(arm, side + "_clear")
            robot.signal(side + "_ready", item_id=side + "_part")
        async def consume(arm, peer):
            side = arm.lower()
            receipt = await robot.wait_event(peer + "_ready", 20)
            await robot.move(arm, side + "_pickup_wait")
            await robot.move(arm, peer + "_pad")
            await robot.grasp(arm, peer + "_part")
            await robot.move(arm, side + "_target", receipt=receipt)
            robot.clear_event(peer + "_ready", expected_version=receipt.version)
            await robot.release(arm, peer + "_part", side + "_target")
            await robot.move(arm, side + "_depart")
        await deposit("LEFT")
        await deposit("RIGHT")
        await consume("LEFT", "right")
        await consume("RIGHT", "left")
    async def _rq2_producer():
        return robot.signal("rq2_gate")
    async def _rq2_consumer():
        receipt = await robot.wait_event("rq2_gate", 20)
        await _rq2_mission()
        robot.clear_event("rq2_gate", expected_version=receipt.version)
    for _round in range(1):
        if _round == 0:
            await asyncio.gather(_rq2_producer(), _rq2_consumer())
