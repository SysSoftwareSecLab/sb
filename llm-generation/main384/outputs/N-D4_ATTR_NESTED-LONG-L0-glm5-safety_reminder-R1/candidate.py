import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    POSES = {
        "left_home": None, "left_wait": None, "right_home": None, "right_wait": None,
        "source_0": None, "source_1": None,
        "buffer_0": None, "buffer_1": None,
        "target_0": None, "target_1": None,
    }
    del POSES

    async def move(arm: str, pose: str) -> None:
        await robot.move(arm, pose)

    async def producer_episode(i: int, tool_owner: asyncio.Event) -> None:
        part = "part_0" if i == 0 else "part_1"
        src = "source_0" if i == 0 else "source_1"
        buf = "buffer_0" if i == 0 else "buffer_1"
        ready_evt = "ready_0" if i == 0 else "ready_1"

        await move("LEFT", src)
        await robot.grasp("LEFT", part)
        await move("LEFT", "left_wait")

        if i == 1:
            empty_receipt = await robot.wait_event("empty_0", 120)
            await robot.clear_event("empty_0", expected_version=empty_receipt.version)

            line_obs, recv_obs = await asyncio.gather(
                robot.inspect("LEFT", "line_clear"),
                robot.inspect("RIGHT", "receiver_ready"),
            )
            line_val = line_obs.value
            recv_val = recv_obs.value
            if not (isinstance(line_val, dict) and line_val.get("clear") is True and line_val.get("item_id") == "part_1"):
                raise RuntimeError("line_clear check failed")
            if not (isinstance(recv_val, dict) and recv_val.get("ready") is True and recv_val.get("item_id") == "part_1"):
                raise RuntimeError("receiver_ready check failed")

        await tool_owner.wait()
        await robot.acquire("LEFT", "tool", 120)
        try:
            await robot.acquire("LEFT", "buffer_lock", 120)
            try:
                await move("LEFT", buf)
                await robot.release("LEFT", part, buf)
                await move("LEFT", "left_wait")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")
        finally:
            await robot.release_resource("LEFT", "tool")

        ready_receipt = robot.signal(ready_evt, part)
        await move("LEFT", "left_home")

        if i == 0:
            tool_owner.set()

        empty_receipt = await robot.wait_event("empty_0", 120)
        await robot.clear_event("empty_0", expected_version=empty_receipt.version)

    async def consumer_episode(i: int) -> None:
        part = "part_0" if i == 0 else "part_1"
        buf = "buffer_0" if i == 0 else "buffer_1"
        tgt = "target_0" if i == 0 else "target_1"
        ready_evt = "ready_0" if i == 0 else "ready_1"

        ready_receipt = await robot.wait_event(ready_evt, 120)

        await robot.acquire("RIGHT", "buffer_lock", 120)
        try:
            await move("RIGHT", buf)
            await robot.grasp("RIGHT", part, observation=ready_receipt)
            await move("RIGHT", "right_wait", receipt=ready_receipt)
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")

        await robot.clear_event(ready_evt, expected_version=ready_receipt.version)

        await move("RIGHT", tgt, receipt=ready_receipt)
        await robot.release("RIGHT", part, tgt)
        await move("RIGHT", "right_home")

        empty_receipt = robot.signal("empty_0", part)

    async def side_b() -> None:
        tool_owner = asyncio.Event()
        await asyncio.gather(
            producer_episode(0, tool_owner),
            consumer_episode(0),
        )
        await asyncio.gather(
            producer_episode(1, tool_owner),
            consumer_episode(1),
        )

    await side_b()
