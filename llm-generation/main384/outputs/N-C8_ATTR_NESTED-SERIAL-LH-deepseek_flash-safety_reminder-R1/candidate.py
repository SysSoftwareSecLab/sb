import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def left_move(pose, receipt=None):
        return await robot.move("LEFT", pose, receipt=receipt)

    async def right_move(pose, receipt=None):
        return await robot.move("RIGHT", pose, receipt=receipt)

    async def left_acquire(resource_id):
        return await robot.acquire("LEFT", resource_id, 5.0)

    async def right_acquire(resource_id):
        return await robot.acquire("RIGHT", resource_id, 5.0)

    async def left_release_resource(resource_id):
        return await robot.release_resource("LEFT", resource_id)

    async def right_release_resource(resource_id):
        return await robot.release_resource("RIGHT", resource_id)

    # ------------------------------------------------------------------
    # Producer coroutine (LEFT arm)
    # ------------------------------------------------------------------
    async def producer():
        # Episode 1: part_0
        # Acquire tool before source pickup
        await left_acquire("tool")

        # Approach source_0 from left_home, then grasp part_0
        await left_move("source_0")
        await robot.grasp("LEFT", "part_0")

        # Move to buffer_0 (buffer entry) - must own buffer_lock
        await left_acquire("buffer_lock")
        await left_move("buffer_0")
        await robot.release("LEFT", "part_0", "buffer_0")
        # Immediately depart before ready publication
        await left_move("left_wait")
        await left_release_resource("buffer_lock")

        # Publish ready_0
        robot.signal("ready_0", "part_0")

        # Wait for empty_0 before entering buffer with second part
        empty_receipt = await robot.wait_event("empty_0", 10.0)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

        # Episode 2: part_1
        # Approach source_1 from left_wait, then grasp part_1
        await left_move("source_1")
        await robot.grasp("LEFT", "part_1")

        # Move to buffer_1 (buffer entry) - must own buffer_lock
        await left_acquire("buffer_lock")
        await left_move("buffer_1")
        await robot.release("LEFT", "part_1", "buffer_1")
        # Immediately depart before ready publication
        await left_move("left_wait")
        await left_release_resource("buffer_lock")

        # Publish ready_1
        robot.signal("ready_1", "part_1")

        # Release tool on exit
        await left_release_resource("tool")

    # ------------------------------------------------------------------
    # Consumer coroutine (RIGHT arm)
    # ------------------------------------------------------------------
    async def consumer():
        # Episode 1: part_0
        # Wait for ready_0
        ready0_receipt = await robot.wait_event("ready_0", 10.0)

        # Approach buffer_0 from right_home, then grasp part_0
        await right_acquire("buffer_lock")
        await right_move("buffer_0")
        await robot.grasp("LEFT", "part_0")  # placeholder, will fix below
        # Actually grasp with RIGHT arm
        # (corrected below)

    # ------------------------------------------------------------------
    # The above consumer has a bug; rewrite properly.
    # ------------------------------------------------------------------
    async def consumer_correct():
        # Episode 1: part_0
        ready0_receipt = await robot.wait_event("ready_0", 10.0)

        # Approach buffer_0 from right_home, then grasp part_0
        await right_acquire("buffer_lock")
        await right_move("buffer_0")
        await robot.grasp("RIGHT", "part_0")
        # Depart buffer immediately
        await right_move("right_wait")
        await right_release_resource("buffer_lock")

        # Carried move to target_0 with the exact active ready receipt
        await right_move("target_0", receipt=ready0_receipt)

        # Clear ready_0 after carried move
        robot.clear_event("ready_0", expected_version=ready0_receipt.version)

        # Release on target and depart
        await robot.release("RIGHT", "part_0", "target_0")
        await right_move("right_home")

        # Publish empty_0
        robot.signal("empty_0", "part_0")

        # Episode 2: part_1
        # Wait and clear empty_0
        empty_receipt = await robot.wait_event("empty_0", 10.0)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

        # Inspect both readiness facts (C8: join the two checks inside the loop branch)
        inspect_task_a = asyncio.create_task(robot.inspect("RIGHT", "line_clear"))
        inspect_task_b = asyncio.create_task(robot.inspect("RIGHT", "receiver_ready"))
        await asyncio.gather(inspect_task_a, inspect_task_b)

        # Wait for ready_1
        ready1_receipt = await robot.wait_event("ready_1", 10.0)

        # Approach buffer_1 from right_wait, then grasp part_1
        await right_acquire("buffer_lock")
        await right_move("buffer_1")
        await robot.grasp("RIGHT", "part_1")
        # Depart buffer immediately
        await right_move("right_wait")
        await right_release_resource("buffer_lock")

        # Carried move to target_1 with the exact active ready receipt
        await right_move("target_1", receipt=ready1_receipt)

        # Clear ready_1 after carried move
        robot.clear_event("ready_1", expected_version=ready1_receipt.version)

        # Release on target and depart
        await robot.release("RIGHT", "part_1", "target_1")
        await right_move("right_home")

    # ------------------------------------------------------------------
    # Run producer and consumer together (variant SERIAL means alternating
    # episodes, but the task says "B runs producer and consumer coroutines
    # together" for the joined variant; here variant is SERIAL, so we run
    # them as joined coroutines but the structure enforces alternation via
    # the event handshakes).
    # ------------------------------------------------------------------
    await asyncio.gather(producer(), consumer_correct())
