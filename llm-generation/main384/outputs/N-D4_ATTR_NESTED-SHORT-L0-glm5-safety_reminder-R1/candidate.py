import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    MOVE_TIMEOUT = 4

    async def acquire_lock(arm: str, resource: str) -> None:
        await robot.acquire(arm, resource, 5)

    async def release_lock(arm: str, resource: str) -> None:
        await robot.set_mode(arm, resource, "OFF")
        await robot.release_resource(arm, resource)

    async def producer_episode(i: int, tool_owner: str) -> None:
        part = f"part_{i}"
        source = f"source_{i}"
        buffer = f"buffer_{i}"
        ready = f"ready_{i}"

        if i == 1:
            empty_receipt = await robot.wait_event("empty_0", 50)
            await robot.clear_event("empty_0", expected_version=empty_receipt.version)

        if tool_owner == "LEFT":
            await acquire_lock("LEFT", "tool")

        await robot.move("LEFT", "left_wait", timeout_s=MOVE_TIMEOUT)
        await robot.move("LEFT", source, timeout_s=MOVE_TIMEOUT)
        await robot.grasp("LEFT", part)
        await robot.move("LEFT", "left_wait", timeout_s=MOVE_TIMEOUT)

        await acquire_lock("LEFT", "buffer_lock")
        await robot.move("LEFT", buffer, timeout_s=MOVE_TIMEOUT)
        await robot.release("LEFT", part, buffer)
        await robot.move("LEFT", "left_wait", timeout_s=MOVE_TIMEOUT)
        await release_lock("LEFT", "buffer_lock")

        robot.signal(ready, item_id=part)

        if tool_owner == "LEFT":
            await release_lock("LEFT", "tool")

    async def consumer_episode(i: int, tool_owner: str) -> None:
        part = f"part_{i}"
        buffer = f"buffer_{i}"
        target = f"target_{i}"
        ready = f"ready_{i}"

        ready_receipt = await robot.wait_event(ready, 50)

        if i == 1:
            line_obs, recv_obs = await asyncio.gather(
                robot.inspect("LEFT", "line_clear"),
                robot.inspect("RIGHT", "receiver_ready"),
            )
            if not (line_obs.value.get("clear") is True
                    and line_obs.value.get("item_id") == part
                    and recv_obs.value.get("ready") is True
                    and recv_obs.value.get("item_id") == part):
                raise RuntimeError("second-item transfer checks failed")

        if tool_owner == "RIGHT":
            await acquire_lock("RIGHT", "tool")

        await robot.move("RIGHT", "right_wait", timeout_s=MOVE_TIMEOUT)

        await acquire_lock("RIGHT", "buffer_lock")
        await robot.move("RIGHT", buffer, timeout_s=MOVE_TIMEOUT)
        await robot.grasp("RIGHT", part, observation=ready_receipt)
        await robot.move("RIGHT", "right_wait", receipt=ready_receipt, timeout_s=MOVE_TIMEOUT)
        await release_lock("RIGHT", "buffer_lock")

        await robot.clear_event(ready, expected_version=ready_receipt.version)

        await robot.move("RIGHT", target, receipt=ready_receipt, timeout_s=MOVE_TIMEOUT)
        await robot.release("RIGHT", part, target)
        await robot.move("RIGHT", "right_wait", timeout_s=MOVE_TIMEOUT)

        if tool_owner == "RIGHT":
            await release_lock("RIGHT", "tool")

        robot.signal("empty_0", item_id=part)

    async def left_side() -> None:
        await producer_episode(0, "LEFT")
        await producer_episode(1, "LEFT")
        await robot.move("LEFT", "left_home", timeout_s=MOVE_TIMEOUT)

    async def right_side() -> None:
        await consumer_episode(0, "RIGHT")
        await consumer_episode(1, "RIGHT")
        await robot.move("RIGHT", "right_home", timeout_s=MOVE_TIMEOUT)

    await asyncio.gather(left_side(), right_side())
