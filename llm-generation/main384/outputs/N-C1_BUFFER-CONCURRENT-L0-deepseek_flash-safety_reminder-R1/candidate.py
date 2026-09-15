import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # Variant B: producer and consumer coroutines run together.
    # Two parts cross a capacity-one buffer from LEFT producer to RIGHT consumer.
    #
    # Producer (LEFT arm):
    #   part_0: left_home -> source_0 (approach+grasp) -> buffer_0 (release) -> left_wait
    #   part_1: left_wait -> source_1 (approach+grasp) -> buffer_1 (release) -> left_home
    # Consumer (RIGHT arm):
    #   part_0: right_home -> buffer_0 (approach+grasp) -> target_0 (release) -> right_wait
    #   part_1: right_wait -> buffer_1 (approach+grasp) -> target_1 (release) -> right_home
    #
    # Events: ready_0, ready_1 (producer signals, consumer waits/clears)
    #         empty_0 (consumer signals, producer waits/clears)
    # Resource: buffer_lock (both own during buffer entry/departure)

    async def producer() -> None:
        # --- Episode 0: part_0 ---
        # Approach source_0 from left_home, then immediately grasp part_0.
        await robot.move("LEFT", "source_0")
        await robot.grasp("LEFT", "part_0")

        # Acquire buffer_lock, enter buffer, release part_0 at buffer_0, depart.
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", "buffer_0")
        await robot.release("LEFT", "part_0", "buffer_0")
        # Immediate separating departure from buffer.
        await robot.move("LEFT", "left_wait")
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready_0 for the consumer.
        ready0 = robot.signal("ready_0")

        # --- Episode 1: part_1 ---
        # Wait for empty_0 before entering buffer with the second part.
        empty0 = await robot.wait_event("empty_0", 30)
        robot.clear_event("empty_0", expected_version=empty0.version)

        # Approach source_1 from left_wait, then immediately grasp part_1.
        await robot.move("LEFT", "source_1")
        await robot.grasp("LEFT", "part_1")

        # Acquire buffer_lock, enter buffer, release part_1 at buffer_1, depart.
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", "buffer_1")
        await robot.release("LEFT", "part_1", "buffer_1")
        # Immediate separating departure from buffer.
        await robot.move("LEFT", "left_home")
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready_1 for the consumer.
        ready1 = robot.signal("ready_1")

    async def consumer() -> None:
        # --- Episode 0: part_0 ---
        # Wait for ready_0 before pickup.
        ready0 = await robot.wait_event("ready_0", 30)

        # Approach buffer_0 from right_home, then immediately grasp part_0.
        await robot.move("RIGHT", "buffer_0")
        await robot.grasp("RIGHT", "part_0")

        # Acquire buffer_lock, depart buffer, release at target_0.
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.move("RIGHT", "right_wait")
        await robot.release_resource("RIGHT", "buffer_lock")

        # Carried move to target with the exact active item receipt.
        await robot.move("RIGHT", "target_0", receipt=ready0)
        await robot.release("RIGHT", "part_0", "target_0")
        # Immediate separating departure from target.
        await robot.move("RIGHT", "right_wait")

        # Clear ready_0 after carried move and departure, then publish empty_0.
        robot.clear_event("ready_0", expected_version=ready0.version)
        robot.signal("empty_0")

        # --- Episode 1: part_1 ---
        # Wait for ready_1 before pickup.
        ready1 = await robot.wait_event("ready_1", 30)

        # Approach buffer_1 from right_wait, then immediately grasp part_1.
        await robot.move("RIGHT", "buffer_1")
        await robot.grasp("RIGHT", "part_1")

        # Acquire buffer_lock, depart buffer, release at target_1.
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.move("RIGHT", "right_home")
        await robot.release_resource("RIGHT", "buffer_lock")

        # Carried move to target with the exact active item receipt.
        await robot.move("RIGHT", "target_1", receipt=ready1)
        await robot.release("RIGHT", "part_1", "target_1")
        # Immediate separating departure from target.
        await robot.move("RIGHT", "right_home")

        # Clear ready_1 after carried move and departure.
        robot.clear_event("ready_1", expected_version=ready1.version)

    # Run producer and consumer coroutines together (joined concurrency).
    await asyncio.gather(producer(), consumer())
