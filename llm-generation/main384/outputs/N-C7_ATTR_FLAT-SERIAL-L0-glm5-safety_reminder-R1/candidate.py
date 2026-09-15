import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    MOVE_TIMEOUT = 4

    async def acquire_lock(arm: str) -> None:
        await robot.acquire(arm, "buffer_lock", 120)

    async def release_lock(arm: str) -> None:
        await robot.release_resource(arm, "buffer_lock")

    async def acquire_tool(arm: str) -> None:
        await robot.acquire(arm, "tool", 120)

    async def release_tool(arm: str) -> None:
        await robot.release_resource(arm, "tool")

    async def producer_episode(part: str, source: str, ready_event: str) -> None:
        await robot.move("LEFT", "left_home", MOVE_TIMEOUT)
        await acquire_tool("LEFT")
        await robot.move("LEFT", source, MOVE_TIMEOUT)
        await robot.grasp("LEFT", part)
        await robot.move("LEFT", "left_home", MOVE_TIMEOUT)
        await acquire_lock("LEFT")
        await robot.move("LEFT", "buffer_0", MOVE_TIMEOUT)
        await robot.release("LEFT", part, "buffer_0")
        await robot.move("LEFT", "left_home", MOVE_TIMEOUT)
        await release_lock("LEFT")
        receipt = robot.signal(ready_event, part)
        await robot.wait_event(ready_event, 120)
        await robot.clear_event(ready_event, expected_version=receipt.version)
        await release_tool("LEFT")

    async def consumer_episode(part: str, target: str, ready_event: str) -> None:
        receipt = await robot.wait_event(ready_event, 120)
        await acquire_lock("RIGHT")
        await robot.move("RIGHT", "buffer_0", MOVE_TIMEOUT, receipt=receipt)
        await robot.grasp("RIGHT", part)
        await robot.move("RIGHT", "right_home", MOVE_TIMEOUT, receipt=receipt)
        await robot.clear_event(ready_event, expected_version=receipt.version)
        await robot.move("RIGHT", target, MOVE_TIMEOUT)
        await robot.release("RIGHT", part, target)
        await robot.move("RIGHT", "right_home", MOVE_TIMEOUT)
        await release_lock("RIGHT")
        empty_receipt = robot.signal("empty_0", part)
        await robot.wait_event("empty_0", 120)
        await robot.clear_event("empty_0", expected_version=empty_receipt.version)

    async def episode_0() -> None:
        await producer_episode("part_0", "source_0", "ready_0")
        await consumer_episode("part_0", "target_0", "ready_0")

    async def episode_1() -> None:
        await robot.move("LEFT", "left_wait", MOVE_TIMEOUT)
        await robot.inspect("LEFT", "line_clear")
        await robot.inspect("LEFT", "receiver_ready")
        await robot.move("LEFT", "source_1", MOVE_TIMEOUT)
        await robot.grasp("LEFT", "part_1")
        await robot.move("LEFT", "left_wait", MOVE_TIMEOUT)
        await acquire_lock("LEFT")
        await robot.move("LEFT", "buffer_1", MOVE_TIMEOUT)
        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.move("LEFT", "left_wait", MOVE_TIMEOUT)
        await release_lock("LEFT")
        ready_receipt = robot.signal("ready_1", "part_1")
        await robot.wait_event("ready_1", 120)
        await robot.clear_event("ready_1", expected_version=ready_receipt.version)
        await release_tool("LEFT")

        consumer_receipt = await robot.wait_event("ready_1", 120)
        await acquire_lock("RIGHT")
        await robot.move("RIGHT", "buffer_1", MOVE_TIMEOUT, receipt=consumer_receipt)
        await robot.grasp("RIGHT", "part_1")
        await robot.move("RIGHT", "right_wait", MOVE_TIMEOUT, receipt=consumer_receipt)
        await robot.clear_event("ready_1", expected_version=consumer_receipt.version)
        await robot.move("RIGHT", "target_1", MOVE_TIMEOUT)
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home", MOVE_TIMEOUT)
        await release_lock("RIGHT")
        empty_receipt = robot.signal("empty_0", "part_1")
        await robot.wait_event("empty_0", 120)
        await robot.clear_event("empty_0", expected_version=empty_receipt.version)

    await episode_0()
    await episode_1()
