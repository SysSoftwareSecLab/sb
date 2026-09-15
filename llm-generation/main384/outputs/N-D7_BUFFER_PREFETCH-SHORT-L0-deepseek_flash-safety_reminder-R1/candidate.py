import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # Producer coroutine: LEFT arm moves parts from sources to buffer.
    async def producer() -> None:
        # Part 0: source_0 -> buffer_0
        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "source_0")
        obs0 = await robot.grasp("LEFT", "part_0")
        await robot.move("LEFT", "buffer_0")
        await robot.release("LEFT", "part_0", "buffer_0")
        await robot.move("LEFT", "left_wait")
        robot.signal("ready_0", "part_0")

        # Wait for empty_0 before second part
        receipt_empty = await robot.wait_event("empty_0", 30)
        robot.clear_event("empty_0", expected_version=receipt_empty.version)

        # Part 1: source_1 -> buffer_1
        await robot.move("LEFT", "source_1")
        obs1 = await robot.grasp("LEFT", "part_1")
        await robot.move("LEFT", "buffer_1")
        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.move("LEFT", "left_home")

    # Consumer coroutine: RIGHT arm moves parts from buffer to targets.
    async def consumer() -> None:
        # Part 0: buffer_0 -> target_0
        receipt_ready0 = await robot.wait_event("ready_0", 30)
        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", "buffer_0")
        obs0 = await robot.grasp("RIGHT", "part_0", observation=receipt_ready0)
        await robot.move("RIGHT", "target_0", receipt=receipt_ready0)
        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_wait")
        robot.clear_event("ready_0", expected_version=receipt_ready0.version)
        robot.signal("empty_0")

        # Part 1: buffer_1 -> target_1
        receipt_ready1 = await robot.wait_event("ready_1", 30)
        await robot.move("RIGHT", "buffer_1")
        obs1 = await robot.grasp("RIGHT", "part_1", observation=receipt_ready1)
        await robot.move("RIGHT", "target_1", receipt=receipt_ready1)
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home")
        robot.clear_event("ready_1", expected_version=receipt_ready1.version)

    # Run producer and consumer concurrently (variant B).
    await asyncio.gather(producer(), consumer())
