import asyncio
import json

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- Constants from the public task ----
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    PARTS = ["part_0", "part_1"]
    SOURCES = {"part_0": "source_0", "part_1": "source_1"}
    TARGETS = {"part_0": "target_0", "part_1": "target_1"}
    BUFFER_POSES = {"part_0": "buffer_0", "part_1": "buffer_1"}

    READY_EVENTS = {"part_0": "ready_0", "part_1": "ready_1"}
    EMPTY_EVENT = "empty_0"

    BUFFER_LOCK = "buffer_lock"
    TOOL = "tool"

    LEFT_HOME = "left_home"
    RIGHT_HOME = "right_home"
    LEFT_WAIT = "left_wait"
    RIGHT_WAIT = "right_wait"

    ACQUIRE_TIMEOUT = 120
    MOVE_TIMEOUT = 4

    # ---- Shared state ----
    empty_receipt_box: dict[str, object] = {}
    ready_receipts: dict[str, object] = {}
    empty_consumed = asyncio.Event()
    empty_consumed.set()  # initially empty_0 is inactive; producer may enter first part

    # ---- Helpers ----
    async def acquire_lock(arm: str, resource: str) -> None:
        await robot.acquire(arm, resource, ACQUIRE_TIMEOUT)

    async def release_lock(arm: str, resource: str) -> None:
        await robot.set_mode(arm, resource, "OFF")
        await robot.release_resource(arm, resource)

    async def move_to(arm: str, pose: str) -> None:
        await robot.move(arm, pose, MOVE_TIMEOUT)

    # ---- Producer coroutine (LEFT arm) ----
    async def producer() -> None:
        # First part: no need to wait for empty_0 (buffer is initially empty).
        await produce_part("part_0", wait_for_empty=False)

        # Second part: wait for empty_0, clear it, then inspect readiness facts.
        await produce_part("part_1", wait_for_empty=True)

        # Return home.
        await move_to(LEFT, LEFT_HOME)

    async def produce_part(part: str, wait_for_empty: bool) -> None:
        source = SOURCES[part]
        buffer_pose = BUFFER_POSES[part]
        ready_event = READY_EVENTS[part]

        if wait_for_empty:
            # Wait for empty_0 signal from consumer, then clear it.
            empty_receipt = await robot.wait_event(EMPTY_EVENT, ACQUIRE_TIMEOUT)
            await robot.clear_event(EMPTY_EVENT, expected_version=empty_receipt.version)

        # Acquire tool for source pickup through ready publication.
        await acquire_lock(LEFT, TOOL)

        # Approach source and grasp immediately (no intervening calls).
        await move_to(LEFT, source)
        await robot.grasp(LEFT, part)

        # Carry part to buffer.
        await move_to(LEFT, buffer_pose)

        # Acquire buffer_lock for entry and departure.
        await acquire_lock(LEFT, BUFFER_LOCK)

        # Release part on buffer.
        await robot.release(LEFT, part, buffer_pose)

        # Immediately depart buffer.
        await move_to(LEFT, LEFT_WAIT)

        # Release buffer_lock on exit.
        await release_lock(LEFT, BUFFER_LOCK)

        # Publish ready event for this part.
        ready_receipt = robot.signal(ready_event, part)
        ready_receipts[part] = ready_receipt

        # Release tool on exit.
        await release_lock(LEFT, TOOL)

    # ---- Consumer coroutine (RIGHT arm) ----
    async def consumer() -> None:
        await consume_part("part_0")
        await consume_part("part_1")

        # Return home.
        await move_to(RIGHT, RIGHT_HOME)

    async def consume_part(part: str) -> None:
        target = TARGETS[part]
        buffer_pose = BUFFER_POSES[part]
        ready_event = READY_EVENTS[part]

        # Wait for the corresponding ready receipt before pickup.
        ready_receipt = await robot.wait_event(ready_event, ACQUIRE_TIMEOUT)

        # Move to right_wait before entering buffer.
        await move_to(RIGHT, RIGHT_WAIT)

        # Acquire buffer_lock for entry and departure.
        await acquire_lock(RIGHT, BUFFER_LOCK)

        # Approach buffer and grasp immediately.
        await move_to(RIGHT, buffer_pose)
        await robot.grasp(RIGHT, part)

        # Depart buffer immediately.
        await move_to(RIGHT, RIGHT_WAIT)

        # Release buffer_lock on exit.
        await release_lock(RIGHT, BUFFER_LOCK)

        # Clear ready after carried move begins; supply exact active item receipt on move to target.
        await robot.clear_event(ready_event, expected_version=ready_receipt.version)
        await move_to(RIGHT, target, MOVE_TIMEOUT, receipt=ready_receipt)

        # Release on target and depart before publishing empty_0.
        await robot.release(RIGHT, part, target)
        await move_to(RIGHT, RIGHT_WAIT)

        # Publish empty_0.
        empty_receipt = robot.signal(EMPTY_EVENT, part)
        empty_receipt_box["receipt"] = empty_receipt

    # ---- Run producer and consumer concurrently ----
    await asyncio.gather(producer(), consumer())
