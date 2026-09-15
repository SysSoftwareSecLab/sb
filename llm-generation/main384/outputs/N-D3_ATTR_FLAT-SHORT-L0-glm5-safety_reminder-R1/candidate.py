import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    TOOL = "tool"
    LOCK = "buffer_lock"

    EMPTY_EVENT = "empty_0"
    READY_EVENTS = ("ready_0", "ready_1")
    ITEMS = ("part_0", "part_1")

    SOURCE_POSES = ("source_0", "source_1")
    BUFFER_POSES = ("buffer_0", "buffer_1")
    TARGET_POSES = ("target_0", "target_1")

    LEFT_HOME = "left_home"
    RIGHT_HOME = "right_home"
    LEFT_WAIT = "left_wait"
    RIGHT_WAIT = "right_wait"

    ACQUIRE_TIMEOUT = 120
    MOVE_TIMEOUT = 30
    WAIT_TIMEOUT = 120

    async def producer_episode(i: int) -> None:
        item = ITEMS[i]
        source = SOURCE_POSES[i]
        buffer = BUFFER_POSES[i]

        await robot.acquire(LEFT, TOOL, ACQUIRE_TIMEOUT)
        try:
            await robot.move(LEFT, LEFT_HOME, MOVE_TIMEOUT)
            await robot.move(LEFT, source, MOVE_TIMEOUT)
            await robot.grasp(LEFT, item)
            await robot.move(LEFT, LEFT_HOME, MOVE_TIMEOUT)

            await robot.acquire(LEFT, LOCK, ACQUIRE_TIMEOUT)
            try:
                await robot.move(LEFT, buffer, MOVE_TIMEOUT)
                await robot.release(LEFT, item, buffer)
                await robot.move(LEFT, LEFT_WAIT, MOVE_TIMEOUT)
            finally:
                await robot.set_mode(LEFT, LOCK, "OFF")
                await robot.release_resource(LEFT, LOCK)

            robot.signal(READY_EVENTS[i])
        finally:
            await robot.set_mode(LEFT, TOOL, "OFF")
            await robot.release_resource(LEFT, TOOL)

    async def consumer_episode(i: int) -> None:
        item = ITEMS[i]
        buffer = BUFFER_POSES[i]
        target = TARGET_POSES[i]

        ready_receipt = await robot.wait_event(READY_EVENTS[i], WAIT_TIMEOUT)

        await robot.acquire(RIGHT, TOOL, ACQUIRE_TIMEOUT)
        try:
            await robot.move(RIGHT, RIGHT_HOME, MOVE_TIMEOUT)
            await robot.move(RIGHT, RIGHT_WAIT, MOVE_TIMEOUT)
            await robot.move(RIGHT, buffer, MOVE_TIMEOUT, receipt=ready_receipt)
            await robot.grasp(RIGHT, item)
            await robot.move(RIGHT, RIGHT_WAIT, MOVE_TIMEOUT)

            clear_event(READY_EVENTS[i], expected_version=ready_receipt.version)

            await robot.acquire(RIGHT, LOCK, ACQUIRE_TIMEOUT)
            try:
                await robot.move(RIGHT, target, MOVE_TIMEOUT)
                await robot.release(RIGHT, item, target)
                await robot.move(RIGHT, RIGHT_HOME, MOVE_TIMEOUT)
            finally:
                await robot.set_mode(RIGHT, LOCK, "OFF")
                await robot.release_resource(RIGHT, LOCK)

            robot.signal(EMPTY_EVENT)
        finally:
            await robot.set_mode(RIGHT, TOOL, "OFF")
            await robot.release_resource(RIGHT, TOOL)

    async def producer_second_entry() -> None:
        empty_receipt = await robot.wait_event(EMPTY_EVENT, WAIT_TIMEOUT)
        clear_event(EMPTY_EVENT, expected_version=empty_receipt.version)

        line_clear_obs = await robot.inspect(LEFT, "line_clear")
        receiver_ready_obs = await robot.refresh(RIGHT, "receiver_ready")

        line_clear_value = line_clear_obs.value
        receiver_ready_value = receiver_ready_obs.value

        if not (
            isinstance(line_clear_value, dict)
            and line_clear_value.get("clear") is True
            and line_clear_value.get("item_id") == ITEMS[1]
        ):
            raise RuntimeError("line_clear check failed for second item")

        if not (
            isinstance(receiver_ready_value, dict)
            and receiver_ready_value.get("ready") is True
            and receiver_ready_value.get("item_id") == ITEMS[1]
        ):
            raise RuntimeError("receiver_ready check failed for second item")

        await producer_episode(1)

    async def consumer_second(i: int) -> None:
        await consumer_episode(i)

    async def arm_a() -> None:
        await producer_episode(0)
        await asyncio.sleep(0)
        await consumer_second(0)
        await producer_second_entry()
        await asyncio.sleep(0)
        await consumer_second(1)

    async def arm_b() -> None:
        await consumer_second(0)
        await asyncio.sleep(0)
        await producer_second_entry()
        await asyncio.sleep(0)
        await consumer_second(1)

    await asyncio.gather(arm_a(), arm_b())
