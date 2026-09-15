import asyncio

from bridge_robot_api import MotionFault


async def run_task(robot):
    DEFAULT_MOVE_TIMEOUT = 4
    ACQUIRE_TIMEOUT = 5

    LEFT = "LEFT"
    RIGHT = "RIGHT"

    PARTS = ["part_0", "part_1"]
    SOURCES = {"part_0": "source_0", "part_1": "source_1"}
    BUFFERS = {"part_0": "buffer_0", "part_1": "buffer_1"}
    TARGETS = {"part_0": "target_0", "part_1": "target_1"}
    READY_EVENTS = {"part_0": "ready_0", "part_1": "ready_1"}

    BUFFER_LOCK = "buffer_lock"
    TOOL = "tool"
    EMPTY_EVENT = "empty_0"
    RQ2_GATE = "rq2_gate"
    GAPS = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]

    LEFT_HOME = "left_home"
    RIGHT_HOME = "right_home"
    LEFT_WAIT = "left_wait"
    RIGHT_WAIT = "right_wait"

    def signal(event_id, item_id=None):
        return robot.signal(event_id, item_id)

    def clear_event(event_id, expected_version):
        robot.clear_event(event_id, expected_version=expected_version)

    async def move(arm, pose, timeout_s=None, receipt=None):
        if timeout_s is None:
            return await robot.move(arm, pose, timeout_s=None, receipt=receipt)
        return await robot.move(arm, pose, timeout_s=timeout_s, receipt=receipt)

    async def producer_episode(part):
        src = SOURCES[part]
        buf = BUFFERS[part]
        ready_evt = READY_EVENTS[part]

        await acquire(LEFT, TOOL, ACQUIRE_TIMEOUT)

        await move(LEFT, LEFT_WAIT, timeout_s=DEFAULT_MOVE_TIMEOUT)
        await move(LEFT, src, timeout_s=DEFAULT_MOVE_TIMEOUT)
        await robot.grasp(LEFT, part)
        await move(LEFT, LEFT_WAIT, timeout_s=DEFAULT_MOVE_TIMEOUT)

        await acquire(LEFT, BUFFER_LOCK, ACQUIRE_TIMEOUT)

        await move(LEFT, buf, timeout_s=DEFAULT_MOVE_TIMEOUT)
        await robot.release(LEFT, part, buf)
        await move(LEFT, LEFT_WAIT, timeout_s=DEFAULT_MOVE_TIMEOUT)

        release_resource(LEFT, BUFFER_LOCK)

        ready_receipt = signal(ready_evt, part)
        return ready_receipt

    async def consumer_episode(part, ready_receipt):
        buf = BUFFERS[part]
        tgt = TARGETS[part]

        await robot.wait_event(READY_EVENTS[part], 30)

        await acquire(LEFT, BUFFER_LOCK, ACQUIRE_TIMEOUT)

        await move(RIGHT, RIGHT_WAIT, timeout_s=DEFAULT_MOVE_TIMEOUT)
        await move(RIGHT, buf, timeout_s=DEFAULT_MOVE_TIMEOUT)
        await robot.grasp(RIGHT, part)
        await move(RIGHT, RIGHT_WAIT, timeout_s=DEFAULT_MOVE_TIMEOUT)

        release_resource(LEFT, BUFFER_LOCK)

        await move(RIGHT, tgt, timeout_s=DEFAULT_MOVE_TIMEOUT, receipt=ready_receipt)

        clear_event(READY_EVENTS[part], ready_receipt.version)

        await acquire(LEFT, BUFFER_LOCK, ACQUIRE_TIMEOUT)
        await robot.release(RIGHT, part, tgt)
        await move(RIGHT, RIGHT_WAIT, timeout_s=DEFAULT_MOVE_TIMEOUT)
        release_resource(LEFT, BUFFER_LOCK)

        empty_receipt = signal(EMPTY_EVENT, part)
        return empty_receipt

    async def dual_arm_mission():
        # Episode 0: producer and consumer run concurrently.
        prod0_task = asyncio.create_task(producer_episode("part_0"))
        cons0_task = asyncio.create_task(consumer_episode("part_0", None))
        prod0_receipt = await prod0_task

        # Consumer needs the producer's ready receipt for its carried move.
        cons0_task.cancel()
        try:
            await cons0_task
        except (asyncio.CancelledError, Exception):
            pass

        cons0_task = asyncio.create_task(consumer_episode("part_0", prod0_receipt))
        empty0_receipt = await cons0_task

        # Producer waits and clears empty_0 before entering buffer with second part.
        await robot.wait_event(EMPTY_EVENT, 30)
        clear_event(EMPTY_EVENT, empty0_receipt.version)

        # For item 1, inspect both readiness facts after clearing empty_0.
        await robot.inspect(LEFT, "line_clear")
        await robot.inspect(LEFT, "receiver_ready")

        # Episode 1: producer and consumer run concurrently.
        prod1_task = asyncio.create_task(producer_episode("part_1"))
        cons1_task = asyncio.create_task(consumer_episode("part_1", None))
        prod1_receipt = await prod1_task

        cons1_task.cancel()
        try:
            await cons1_task
        except (asyncio.CancelledError, Exception):
            pass

        cons1_task = asyncio.create_task(consumer_episode("part_1", prod1_receipt))
        empty1_receipt = await cons1_task

        await robot.wait_event(EMPTY_EVENT, 30)
        clear_event(EMPTY_EVENT, empty1_receipt.version)

        # Return arms to homes.
        await move(LEFT, LEFT_HOME, timeout_s=DEFAULT_MOVE_TIMEOUT)
        await move(RIGHT, RIGHT_HOME, timeout_s=DEFAULT_MOVE_TIMEOUT)

    async def acquire(arm, resource_id, timeout_s):
        return await robot.acquire(arm, resource_id, timeout_s)

    def release_resource(arm, resource_id):
        return asyncio.ensure_future(robot.release_resource(arm, resource_id))

    async def main_flow():
        # Complete all three rq2_gap resource checks before signalling rq2_gate.
        for gap in GAPS:
            await acquire(LEFT, gap, ACQUIRE_TIMEOUT)
            release_resource(LEFT, gap)

        # Signal rq2_gate exactly once.
        gate_receipt = signal(RQ2_GATE)

        # Wait its exact active receipt exactly once, immediately after signal.
        await robot.wait_event(RQ2_GATE, 30)

        # Keep rq2_gate active while executing the complete inherited dual-arm mission.
        await dual_arm_mission()

        # Clear rq2_gate only after the mission.
        clear_event(RQ2_GATE, gate_receipt.version)

    await main_flow()
