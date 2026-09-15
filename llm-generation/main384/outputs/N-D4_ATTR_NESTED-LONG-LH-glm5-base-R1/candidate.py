import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    async def producer_episode(i: int, tool_acq: asyncio.Future, tool_rel: asyncio.Future):
        part = f"part_{i}"
        source = f"source_{i}"
        buffer = f"buffer_{i}"
        ready = f"ready_{i}"
        empty = "empty_0"

        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", source)
        await robot.grasp("LEFT", part)
        await robot.move("LEFT", "left_home")

        await tool_acq
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", "left_wait")
        await robot.move("LEFT", buffer)
        await robot.release("LEFT", part, buffer)
        await robot.move("LEFT", "left_wait")
        await robot.release_resource("LEFT", "buffer_lock")
        await robot.move("LEFT", "left_home")

        robot.signal(ready, part)
        tool_rel.set_result(None)

        await robot.wait_event(empty, 50)
        await robot.clear_event(empty, expected_version=1)
        return

    async def consumer_episode(i: int, tool_acq: asyncio.Future, tool_rel: asyncio.Future):
        part = f"part_{i}"
        buffer = f"buffer_{i}"
        target = f"target_{i}"
        ready = f"ready_{i}"
        empty = "empty_0"

        receipt = await robot.wait_event(ready, 50)
        await robot.clear_event(ready, expected_version=receipt.version)

        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", f"right_wait")
        await robot.move("RIGHT", buffer)
        await robot.grasp("RIGHT", part, observation=receipt)
        await robot.move("RIGHT", f"right_wait")
        await robot.move("RIGHT", target)
        await robot.clear_event(ready, expected_version=receipt.version)
        await robot.release("RIGHT", part, target)
        await robot.move("RIGHT", f"right_wait")
        await robot.move("RIGHT", "right_home")

        robot.signal(empty, part)
        await tool_rel
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.release_resource("RIGHT", "buffer_lock")
        return

    async def second_item_checks():
        lc, rr = await asyncio.gather(
            robot.inspect("LEFT", "line_clear"),
            robot.inspect("RIGHT", "receiver_ready"),
        )
        if not (lc.value.get("clear") and lc.value.get("item_id") == "part_1"):
            raise RuntimeError("line_clear check failed")
        if not (rr.value.get("ready") and rr.value.get("item_id") == "part_1"):
            raise RuntimeError("receiver_ready check failed")
        return

    async def second_item_pipeline():
        p_acq = asyncio.get_running_loop().create_future()
        p_rel = asyncio.get_running_loop().create_future()
        c_acq = asyncio.get_running_loop().create_future()
        c_rel = asyncio.get_running_loop().create_future()

        async def producer_second():
            await robot.move("LEFT", "left_home")
            await robot.move("LEFT", "source_1")
            await robot.grasp("LEFT", "part_1")
            await robot.move("LEFT", "left_home")

            await robot.acquire("LEFT", "tool", 5)
            p_acq.set_result(None)
            await robot.acquire("LEFT", "buffer_lock", 5)
            await robot.move("LEFT", "left_wait")
            await robot.move("LEFT", "buffer_1")
            await robot.release("LEFT", "part_1", "buffer_1")
            await robot.move("LEFT", "left_wait")
            await robot.release_resource("LEFT", "buffer_lock")
            await robot.move("LEFT", "left_home")

            robot.signal("ready_1", "part_1")
            p_rel.set_result(None)

            await robot.wait_event("empty_0", 50)
            await robot.clear_event("empty_0", expected_version=1)
            await second_item_checks()
            await robot.release_resource("LEFT", "tool")
            return

        async def consumer_second():
            receipt = await robot.wait_event("ready_1", 50)
            await robot.clear_event("ready_1", expected_version=receipt.version)

            await robot.move("RIGHT", "right_home")
            await robot.move("RIGHT", "right_wait")
            await robot.move("RIGHT", "buffer_1")
            await robot.grasp("RIGHT", "part_1", observation=receipt)
            await robot.move("RIGHT", "right_wait")
            await robot.move("RIGHT", "target_1")
            await robot.clear_event("ready_1", expected_version=receipt.version)
            await robot.release("RIGHT", "part_1", "target_1")
            await robot.move("RIGHT", "right_wait")
            await robot.move("RIGHT", "right_home")

            robot.signal("empty_0", "part_1")
            await p_rel
            await robot.acquire("RIGHT", "buffer_lock", 5)
            await robot.release_resource("RIGHT", "buffer_lock")
            return

        await asyncio.gather(producer_second(), consumer_second())
        return

    async def first_item_pipeline():
        p_acq = asyncio.get_running_loop().create_future()
        p_rel = asyncio.get_running_loop().create_future()
        c_acq = asyncio.get_running_loop().create_future()
        c_rel = asyncio.get_running_loop().create_future()

        async def producer_first():
            await robot.move("LEFT", "left_home")
            await robot.move("LEFT", "source_0")
            await robot.grasp("LEFT", "part_0")
            await robot.move("LEFT", "left_home")

            await robot.acquire("LEFT", "tool", 5)
            p_acq.set_result(None)
            await robot.acquire("LEFT", "buffer_lock", 5)
            await robot.move("LEFT", "left_wait")
            await robot.move("LEFT", "buffer_0")
            await robot.release("LEFT", "part_0", "buffer_0")
            await robot.move("LEFT", "left_wait")
            await robot.release_resource("LEFT", "buffer_lock")
            await robot.move("LEFT", "left_home")

            robot.signal("ready_0", "part_0")
            p_rel.set_result(None)

            await robot.wait_event("empty_0", 50)
            await robot.clear_event("empty_0", expected_version=1)
            await robot.release_resource("LEFT", "tool")
            return

        async def consumer_first():
            receipt = await robot.wait_event("ready_0", 50)
            await robot.clear_event("ready_0", expected_version=receipt.version)

            await robot.move("RIGHT", "right_home")
            await robot.move("RIGHT", "right_wait")
            await robot.move("RIGHT", "buffer_0")
            await robot.grasp("RIGHT", "part_0", observation=receipt)
            await robot.move("RIGHT", "right_wait")
            await robot.move("RIGHT", "target_0")
            await robot.clear_event("ready_0", expected_version=receipt.version)
            await robot.release("RIGHT", "part_0", "target_0")
            await robot.move("RIGHT", "right_wait")
            await robot.move("RIGHT", "right_home")

            robot.signal("empty_0", "part_0")
            await p_rel
            await robot.acquire("RIGHT", "buffer_lock", 5)
            await robot.release_resource("RIGHT", "buffer_lock")
            return

        await asyncio.gather(producer_first(), consumer_first())
        return

    await first_item_pipeline()
    await second_item_pipeline()
    return
