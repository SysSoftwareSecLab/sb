import asyncio
from bridge_robot_api import MotionFault


async def run_task(robot):
    # Public task constants (from PUBLIC TASK SPEC).
    LEFT, RIGHT = "LEFT", "RIGHT"
    PART_0, PART_1 = "part_0", "part_1"
    SOURCE_0, SOURCE_1 = "source_0", "source_1"
    BUFFER_0, BUFFER_1 = "buffer_0", "buffer_1"
    TARGET_0, TARGET_1 = "target_0", "target_1"
    LEFT_HOME, RIGHT_HOME = "left_home", "right_home"
    LEFT_WAIT, RIGHT_WAIT = "left_wait", "right_wait"
    READY_0, READY_1 = "ready_0", "ready_1"
    EMPTY_0 = "empty_0"
    BUFFER_LOCK, TOOL = "buffer_lock", "tool"
    LINE_CLEAR, RECEIVER_READY = "line_clear", "receiver_ready"

    # C7: serially check readiness facts inside the loop branch for item 1.
    async def inspect_both_readiness_facts():
        await robot.inspect(RIGHT, LINE_CLEAR)
        await robot.inspect(RIGHT, RECEIVER_READY)

    async def producer_episode(part, source, buffer, ready_event):
        # LEFT owns tool from before each source pickup through ready publication.
        await robot.acquire(LEFT, TOOL, 5)
        await robot.move(LEFT, LEFT_HOME, 4)
        await robot.move(LEFT, source, 4)
        await robot.grasp(LEFT, part)
        await robot.move(LEFT, LEFT_HOME, 4)

        # Producer waits and clears empty_0 before entering buffer with the second part.
        if part == PART_1:
            empty_receipt = await robot.wait_event(EMPTY_0, 5)
            await robot.acquire(LEFT, BUFFER_LOCK, 5)
            try:
                await robot.move(LEFT, buffer, 4, receipt=empty_receipt)
            finally:
                await robot.release_resource(LEFT, BUFFER_LOCK)
        else:
            await robot.acquire(LEFT, BUFFER_LOCK, 5)
            try:
                await robot.move(LEFT, buffer, 4)
            finally:
                await robot.release_resource(LEFT, BUFFER_LOCK)

        await robot.release(LEFT, part, buffer)
        await robot.move(LEFT, LEFT_HOME, 4)
        await robot.release_resource(LEFT, TOOL)
        # Producer places each part at buffer and immediately departs before ready publication.
        ready_receipt = robot.signal(ready_event, part)
        return ready_receipt

    async def consumer_episode(part, buffer, target, ready_event):
        # Consumer waits the corresponding ready receipt before pickup.
        ready_receipt = await robot.wait_event(ready_event, 5)

        await robot.move(RIGHT, RIGHT_HOME, 4)
        await robot.acquire(RIGHT, BUFFER_LOCK, 5)
        try:
            await robot.move(RIGHT, buffer, 4)
        finally:
            await robot.release_resource(RIGHT, BUFFER_LOCK)

        await robot.grasp(RIGHT, part, observation=ready_receipt)
        await robot.move(RIGHT, RIGHT_HOME, 4)

        # Consumer clears ready after its carried move.
        clear_event(ready_receipt)

        await robot.acquire(RIGHT, BUFFER_LOCK, 5)
        try:
            # supplies that exact active item receipt on carried move to target.
            await robot.move(RIGHT, target, 4, receipt=ready_receipt)
        finally:
            await robot.release_resource(RIGHT, BUFFER_LOCK)

        await robot.release(RIGHT, part, target)
        # Consumer ... departs before publishing empty_0.
        await robot.move(RIGHT, RIGHT_HOME, 4)
        robot.signal(EMPTY_0, part)

    def clear_event(receipt):
        robot.clear_event(receipt.event_id, expected_version=receipt.version)

    async def episode_0():
        ready_receipt = await producer_episode(
            PART_0, SOURCE_0, BUFFER_0, READY_0
        )
        await consumer_episode(PART_0, BUFFER_0, TARGET_0, READY_0)

    async def episode_1():
        ready_receipt = await producer_episode(
            PART_1, SOURCE_1, BUFFER_1, READY_1
        )
        # For item 1, wait and clear empty_0, then inspect both readiness facts.
        empty_receipt = await robot.wait_event(EMPTY_0, 5)
        clear_event(empty_receipt)
        await inspect_both_readiness_facts()
        await consumer_episode(PART_1, BUFFER_1, TARGET_1, READY_1)

    # A alternates complete producer/consumer episodes.
    await episode_0()
    await episode_1()
