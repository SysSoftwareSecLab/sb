import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # Producer coroutine: LEFT arm moves part_0 then part_1 through buffer.
    async def producer() -> None:
        # Episode 1: part_0
        await robot.move("LEFT", "source_0")
        await robot.grasp("LEFT", "part_0")
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", "buffer_0")
        await robot.release("LEFT", "part_0", "buffer_0")
        await robot.move("LEFT", "left_wait")
        await robot.release_resource("LEFT", "buffer_lock")
        robot.signal("ready_0", "part_0")

        # Wait for empty_0 before second part
        receipt_empty = await robot.wait_event("empty_0", 10)
        robot.clear_event("empty_0", expected_version=receipt_empty.version)

        # Episode 2: part_1
        await robot.move("LEFT", "source_1")
        await robot.grasp("LEFT", "part_1")
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", "buffer_1")
        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.move("LEFT", "left_wait")
        await robot.release_resource("LEFT", "buffer_lock")
        robot.signal("ready_1", "part_1")

        await robot.move("LEFT", "left_home")

    # Consumer coroutine: RIGHT arm picks up part_0 then part_1 from buffer.
    async def consumer() -> None:
        # Episode 1: part_0
        receipt_ready_0 = await robot.wait_event("ready_0", 10)
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.move("RIGHT", "buffer_0")
        await robot.grasp("RIGHT", "part_0")
        await robot.move("RIGHT", "right_wait")
        await robot.release_resource("RIGHT", "buffer_lock")
        await robot.move("RIGHT", "target_0", receipt=receipt_ready_0)
        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_home")
        robot.clear_event("ready_0", expected_version=receipt_ready_0.version)
        robot.signal("empty_0")

        # Episode 2: part_1
        receipt_ready_1 = await robot.wait_event("ready_1", 10)
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.move("RIGHT", "buffer_1")
        await robot.grasp("RIGHT", "part_1")
        await robot.move("RIGHT", "right_wait")
        await robot.release_resource("RIGHT", "buffer_lock")
        await robot.move("RIGHT", "target_1", receipt=receipt_ready_1)
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home")
        robot.clear_event("ready_1", expected_version=receipt_ready_1.version)

    # Run producer and consumer concurrently (variant B).
    await asyncio.gather(producer(), consumer())
