import asyncio
async def run_task(robot):
    async def _rq2_mission():
        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "left_target")
        await robot.release("LEFT", "left_part", "left_target")
        await robot.move("LEFT", "left_depart")
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
        receipt = await robot.wait_event("rq2_gate", 20)
        if receipt.version <= 0:
            raise RuntimeError("invalid rq2_gate receipt")
        await _rq2_mission()
        robot.clear_event("rq2_gate", expected_version=receipt.version)
    await _rq2_spacing()
    await _rq2_producer()
    await _rq2_consumer()
