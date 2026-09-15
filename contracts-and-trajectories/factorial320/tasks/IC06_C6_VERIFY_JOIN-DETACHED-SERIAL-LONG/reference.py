import asyncio
async def run_task(robot):
    async def _rq2_mission():
        await robot.inspect("LEFT", "left_verification")
        robot.signal("left_ready", item_id="left_part")
        await robot.inspect("RIGHT", "right_verification")
        robot.signal("right_ready", item_id="left_part")
        l = await robot.wait_event("left_ready", 1)
        r = await robot.wait_event("right_ready", 1)
        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "left_target", receipt=l)
        await robot.release("LEFT", "left_part", "left_target")
        await robot.move("LEFT", "left_depart")
        robot.clear_event("left_ready", expected_version=l.version)
        robot.clear_event("right_ready", expected_version=r.version)
        await robot.move("RIGHT", "right_source")
        await robot.grasp("RIGHT", "right_part")
        await robot.move("RIGHT", "right_target")
        await robot.release("RIGHT", "right_part", "right_target")
        await robot.move("RIGHT", "right_depart")
    async def _rq2_spacing():
        for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
            await robot.acquire("LEFT", resource_id, 20)
            await robot.release_resource("LEFT", resource_id)
    async def _rq2_producer():
        return robot.signal("rq2_gate")
    async def _rq2_consumer():
        await _rq2_spacing()
        receipt = await robot.wait_event("rq2_gate", 20)
        if receipt.version <= 0:
            raise RuntimeError("invalid rq2_gate receipt")
        robot.clear_event("rq2_gate", expected_version=receipt.version)
    await _rq2_producer()
    await _rq2_consumer()
    await _rq2_mission()
