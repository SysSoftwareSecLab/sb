import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot):
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    # ---- Producer A (LEFT): places each part at buffer, departs, publishes ready ----
    async def producer():
        # Episode 1: part_0
        await robot.acquire(LEFT, "buffer_lock", 5)
        await robot.move(LEFT, "source_0")
        obs0 = await robot.grasp(LEFT, "part_0")
        await robot.move(LEFT, "buffer_0")
        await robot.release(LEFT, "part_0", "buffer_0")
        await robot.move(LEFT, "left_home")
        robot.signal("ready_0", "part_0")
        await robot.release_resource(LEFT, "buffer_lock")

        # Wait for consumer to clear empty_0 before entering buffer with second part
        er = await robot.wait_event("empty_0", 50)
        robot.clear_event("empty_0", expected_version=er.version)

        # Episode 2: part_1
        await robot.acquire(LEFT, "buffer_lock", 5)
        await robot.move(LEFT, "left_wait")
        await robot.move(LEFT, "source_1")
        obs1 = await robot.grasp(LEFT, "part_1")
        await robot.move(LEFT, "buffer_1")
        await robot.release(LEFT, "part_1", "buffer_1")
        await robot.move(LEFT, "left_home")
        robot.signal("ready_1", "part_1")
        await robot.release_resource(LEFT, "buffer_lock")

    # ---- Consumer B (RIGHT): waits ready, picks from buffer, carries to target ----
    async def consumer():
        # Episode 1: part_0
        r0 = await robot.wait_event("ready_0", 50)
        await robot.acquire(RIGHT, "buffer_lock", 5)
        await robot.move(RIGHT, "buffer_0", receipt=r0)
        await robot.grasp(RIGHT, "part_0")
        await robot.move(RIGHT, "target_0", receipt=r0)
        robot.clear_event("ready_0", expected_version=r0.version)
        await robot.release(RIGHT, "part_0", "target_0")
        await robot.move(RIGHT, "right_home")
        robot.signal("empty_0", "part_0")
        await robot.release_resource(RIGHT, "buffer_lock")

        # Episode 2: part_1
        r1 = await robot.wait_event("ready_1", 50)
        await robot.acquire(RIGHT, "buffer_lock", 5)
        await robot.move(RIGHT, "right_wait")
        await robot.move(RIGHT, "buffer_1", receipt=r1)
        await robot.grasp(RIGHT, "part_1")
        await robot.move(RIGHT, "target_1", receipt=r1)
        robot.clear_event("ready_1", expected_version=r1.version)
        await robot.release(RIGHT, "part_1", "target_1")
        await robot.move(RIGHT, "right_home")
        await robot.release_resource(RIGHT, "buffer_lock")

    await asyncio.gather(producer(), consumer())
