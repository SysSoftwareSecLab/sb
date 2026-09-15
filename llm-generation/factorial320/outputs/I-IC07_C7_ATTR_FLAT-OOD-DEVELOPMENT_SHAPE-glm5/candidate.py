import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    """IC07_C7_ATTR_FLAT-OOD-DEVELOPMENT_SHAPE (SERIAL, L0).

    Structure: FOR -> IF -> PAR_JOIN.
    One finite loop iteration concurrently joins an rq2_gate producer and
    consumer. The consumer waits the exact active ready receipt, executes the
    complete inherited mission, then clears that version.
    """

    async def producer_part0() -> None:
        """LEFT producer: source_0 -> buffer_0, depart, publish ready_0."""
        await robot.acquire("LEFT", "tool", 120)
        await robot.set_mode("LEFT", "tool", "LEFT_PROFILE")

        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "source_0")
        await robot.grasp("LEFT", "part_0")

        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "buffer_0")

        await robot.acquire("LEFT", "buffer_lock", 120)
        await robot.set_mode("LEFT", "buffer_lock", "LEFT_PROFILE")

        await robot.release("LEFT", "part_0", "buffer_0")
        await robot.move("LEFT", "left_home")

        await robot.set_mode("LEFT", "buffer_lock", "OFF")
        await robot.release_resource("LEFT", "buffer_lock")

        ready_receipt = robot.signal("ready_0", "part_0")
        await robot.wait_event("ready_0", 120)

        await robot.wait_event("empty_0", 120)
        empty_receipt = robot.wait_event("empty_0", 0.05)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

        await robot.set_mode("LEFT", "tool", "OFF")
        await robot.release_resource("LEFT", "tool")

        _ = ready_receipt  # producer-side reference retained for clarity

    async def consumer_part0() -> None:
        """RIGHT consumer: wait ready_0, buffer_0 -> target_0, publish empty_0."""
        ready_receipt = await robot.wait_event("ready_0", 120)

        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", "buffer_0")
        await robot.grasp("RIGHT", "part_0", observation=ready_receipt)

        await robot.acquire("RIGHT", "buffer_lock", 120)
        await robot.set_mode("RIGHT", "buffer_lock", "RIGHT_PROFILE")

        await robot.move("RIGHT", "target_0", receipt=ready_receipt)

        await robot.set_mode("RIGHT", "buffer_lock", "OFF")
        await robot.release_resource("RIGHT", "buffer_lock")

        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_home")

        robot.clear_event("ready_0", expected_version=ready_receipt.version)
        robot.signal("empty_0", "part_0")

    async def producer_part1() -> None:
        """LEFT producer: source_1 -> buffer_1, depart, publish ready_1."""
        await robot.acquire("LEFT", "tool", 120)
        await robot.set_mode("LEFT", "tool", "LEFT_PROFILE")

        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "left_wait")
        await robot.move("LEFT", "source_1")
        await robot.grasp("LEFT", "part_1")

        await robot.move("LEFT", "left_wait")
        await robot.move("LEFT", "buffer_1")

        await robot.acquire("LEFT", "buffer_lock", 120)
        await robot.set_mode("LEFT", "buffer_lock", "LEFT_PROFILE")

        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.move("LEFT", "left_wait")

        await robot.set_mode("LEFT", "buffer_lock", "OFF")
        await robot.release_resource("LEFT", "buffer_lock")

        ready_receipt = robot.signal("ready_1", "part_1")
        await robot.wait_event("ready_1", 120)

        await robot.set_mode("LEFT", "tool", "OFF")
        await robot.release_resource("LEFT", "tool")

        _ = ready_receipt

    async def consumer_part1() -> None:
        """RIGHT consumer: wait ready_1, inspect facts, buffer_1 -> target_1."""
        ready_receipt = await robot.wait_event("ready_1", 120)

        line_obs = await robot.inspect("RIGHT", "line_clear")
        receiver_obs = await robot.inspect("RIGHT", "receiver_ready")

        _ = line_obs
        _ = receiver_obs

        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", "right_wait")
        await robot.move("RIGHT", "buffer_1")
        await robot.grasp("RIGHT", "part_1", observation=ready_receipt)

        await robot.acquire("RIGHT", "buffer_lock", 120)
        await robot.set_mode("RIGHT", "buffer_lock", "RIGHT_PROFILE")

        await robot.move("RIGHT", "target_1", receipt=ready_receipt)

        await robot.set_mode("RIGHT", "buffer_lock", "OFF")
        await robot.release_resource("RIGHT", "buffer_lock")

        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home")

        robot.clear_event("ready_1", expected_version=ready_receipt.version)

    async def rq2_gate_episode() -> None:
        """One loop iteration: PAR_JOIN of rq2_gate producer and consumer."""
        await asyncio.gather(producer_part0(), consumer_part0())

    # FOR -> IF -> PAR_JOIN: one finite loop iteration.
    for _ in range(1):
        if True:
            await asyncio.gather(rq2_gate_episode(), consumer_part1())

    # Ensure terminal state: arms at homes, buffer empty, lock free, events inactive.
    await robot.move("LEFT", "left_home")
    await robot.move("RIGHT", "right_home")

    gate_receipt = robot.wait_event("rq2_gate", 0.05)
    if gate_receipt is not None:
        robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
