import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # Variant B: producer and consumer coroutines run together.
    # Layout LH: LEFT produces part_0 and part_1; RIGHT consumes them.
    # Capacity-one buffer at buffer_0/buffer_1 (same physical location).
    # buffer_lock guards buffer entry/departure for both participants.

    async def producer() -> None:
        # Part 0 episode
        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "source_0")
        await robot.grasp("LEFT", "part_0")
        await robot.move("LEFT", "buffer_0")
        await robot.acquire("LEFT", "buffer_lock", 5.0)
        await robot.release("LEFT", "part_0", "buffer_0")
        await robot.release_resource("LEFT", "buffer_lock")
        await robot.move("LEFT", "left_wait")
        robot.signal("ready_0", "part_0")

        # Wait for empty_0 before second part
        await robot.wait_event("empty_0", 10.0)
        robot.clear_event("empty_0", expected_version=1)

        # Part 1 episode
        await robot.move("LEFT", "left_wait")
        await robot.move("LEFT", "source_1")
        await robot.grasp("LEFT", "part_1")
        await robot.move("LEFT", "buffer_1")
        await robot.acquire("LEFT", "buffer_lock", 5.0)
        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.release_resource("LEFT", "buffer_lock")
        await robot.move("LEFT", "left_wait")
        robot.signal("ready_1", "part_1")

        await robot.move("LEFT", "left_home")

    async def consumer() -> None:
        # Part 0 episode
        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", "right_wait")

        receipt0 = await robot.wait_event("ready_0", 10.0)

        await robot.move("RIGHT", "right_wait")
        await robot.move("RIGHT", "buffer_0")
        await robot.acquire("RIGHT", "buffer_lock", 5.0)
        await robot.grasp("RIGHT", "part_0")
        await robot.release_resource("RIGHT", "buffer_lock")
        await robot.move("RIGHT", "target_0", receipt=receipt0)
        robot.clear_event("ready_0", expected_version=receipt0.version)
        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_wait")
        robot.signal("empty_0")

        # Part 1 episode
        receipt1 = await robot.wait_event("ready_1", 10.0)

        await robot.move("RIGHT", "right_wait")
        await robot.move("RIGHT", "buffer_1")
        await robot.acquire("RIGHT", "buffer_lock", 5.0)
        await robot.grasp("RIGHT", "part_1")
        await robot.release_resource("RIGHT", "buffer_lock")
        await robot.move("RIGHT", "target_1", receipt=receipt1)
        robot.clear_event("ready_1", expected_version=receipt1.version)
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home")

    await asyncio.gather(producer(), consumer())
