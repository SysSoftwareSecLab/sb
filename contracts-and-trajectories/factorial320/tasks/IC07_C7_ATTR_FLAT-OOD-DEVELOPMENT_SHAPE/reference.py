import asyncio
async def run_task(robot):
    async def _rq2_mission():
        async def produce(i):
            item = "part_" + str(i)
            tool_owned = False
            await robot.acquire("LEFT", "tool", 20)
            tool_owned = True
            await robot.move("LEFT", "source_" + str(i))
            await robot.grasp("LEFT", item)
            if i == 1:
                ack = await robot.wait_event("empty_0", 20)
                robot.clear_event("empty_0", expected_version=ack.version)
                left_check = await robot.inspect("LEFT", "line_clear")
                right_check = await robot.inspect("RIGHT", "receiver_ready")
                if not left_check.value["clear"] or not right_check.value["ready"]:
                    raise RuntimeError("readiness contract failed")
            try:
                await robot.acquire("LEFT", "buffer_lock", 20)
                await robot.move("LEFT", "buffer_" + str(i))
                await robot.release("LEFT", item, "buffer_" + str(i))
                await robot.move("LEFT", "left_wait")
                await robot.release_resource("LEFT", "buffer_lock")
                robot.signal("ready_" + str(i), item_id=item)
            finally:
                if tool_owned:
                    await robot.release_resource("LEFT", "tool")
        async def consume(i):
            item = "part_" + str(i)
            receipt = await robot.wait_event("ready_" + str(i), 20)
            await robot.acquire("RIGHT", "buffer_lock", 20)
            await robot.move("RIGHT", "buffer_" + str(i))
            await robot.grasp("RIGHT", item)
            await robot.move("RIGHT", "target_" + str(i), receipt=receipt)
            robot.clear_event("ready_" + str(i), expected_version=receipt.version)
            await robot.release("RIGHT", item, "target_" + str(i))
            await robot.move("RIGHT", "right_wait")
            await robot.release_resource("RIGHT", "buffer_lock")
            if i == 0:
                robot.signal("empty_0", item_id=item)
        for i in range(2):
            await produce(i)
            await consume(i)
        await robot.move("LEFT", "left_home")
        await robot.move("RIGHT", "right_home")
    async def _rq2_producer():
        return robot.signal("rq2_gate")
    async def _rq2_consumer():
        receipt = await robot.wait_event("rq2_gate", 20)
        await _rq2_mission()
        robot.clear_event("rq2_gate", expected_version=receipt.version)
    for _round in range(1):
        if _round == 0:
            await asyncio.gather(_rq2_producer(), _rq2_consumer())
