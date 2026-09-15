import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Shared registry for empty_0 receipts, keyed by item_id.
    empty_receipts: dict[str, object] = {}

    async def producer_episode(part: str, source: str, buffer: str,
                                ready_event: str) -> None:
        """LEFT produces one part: source -> buffer, then signal ready."""
        # LEFT owns tool from before each source pickup through ready
        # publication and releases it on every exit.
        await robot.acquire("LEFT", "tool", 120)
        try:
            # Approach source from left_home; immediately grasp.
            await robot.move("LEFT", source, receipt=None)
            await robot.grasp("LEFT", part)

            # Carry to buffer.  Both participants own buffer_lock during
            # buffer entry and departure.
            await robot.acquire("LEFT", "buffer_lock", 120)
            try:
                await robot.move("LEFT", buffer, receipt=None)
                # Release part onto buffer, then immediately depart.
                await robot.release("LEFT", part, buffer)
                await robot.move("LEFT", "left_home", receipt=None)
            finally:
                await robot.release_resource("LEFT", "buffer_lock")
        finally:
            await robot.release_resource("LEFT", "tool")

        # Producer places each part at buffer and immediately departs
        # before ready publication.
        robot.signal(ready_event, part)

    async def consumer_episode(part: str, buffer: str, target: str,
                               ready_event: str) -> None:
        """RIGHT consumes one part: buffer -> target, then signal empty."""
        # Consumer waits the corresponding ready receipt before pickup.
        ready_receipt = await robot.wait_event(ready_event, 120)

        # Both participants own buffer_lock during buffer entry and
        # departure.
        await robot.acquire("RIGHT", "buffer_lock", 120)
        try:
            # Approach buffer from right_home; immediately grasp.
            await robot.move("RIGHT", buffer, receipt=None)
            await robot.grasp("RIGHT", part, observation=ready_receipt)

            # Carried move to target supplies the exact active item
            # receipt.
            await robot.move("RIGHT", target, receipt=ready_receipt)

            # Consumer clears ready after its carried move, releases on
            # target and departs before publishing empty_0.
            clear_event = getattr(robot, "clear_event")
            clear_event(ready_event, expected_version=ready_receipt.version)

            await robot.release("RIGHT", part, target)
            await robot.move("RIGHT", "right_home", receipt=None)
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")

        # Publish empty_0 for this item so the producer may proceed.
        empty_receipt = robot.signal("empty_0", part)
        empty_receipts[part] = empty_receipt

    async def producer_chain() -> None:
        """A alternates complete producer/consumer episodes."""
        # Produce part_0 first.
        await producer_episode("part_0", "source_0", "buffer_0", "ready_0")

        # For item 1, wait and clear empty_0 before entering buffer with
        # the second part.
        empty_receipt = await robot.wait_event("empty_0", 120)
        clear_event = getattr(robot, "clear_event")
        clear_event("empty_0", expected_version=empty_receipt.version)

        # Inspect both readiness facts (serial checks inside the loop
        # branch for item 1).
        await robot.inspect("LEFT", "line_clear")
        await robot.inspect("LEFT", "receiver_ready")

        # Produce part_1.
        await producer_episode("part_1", "source_1", "buffer_1", "ready_1")

    async def consumer_chain() -> None:
        """B runs producer and consumer coroutines together."""
        # Consume part_0.
        await consumer_episode("part_0", "buffer_0", "target_0", "ready_0")
        # Consume part_1.
        await consumer_episode("part_1", "buffer_1", "target_1", "ready_1")

    async def inherited_mission() -> None:
        """Complete inherited dual-arm buffer mission."""
        await asyncio.gather(producer_chain(), consumer_chain())

    async def rq2_scope() -> None:
        """Signal rq2_gate, do three gap checks, then wait and clear."""
        # Signal rq2_gate exactly once.
        gate_receipt = robot.signal("rq2_gate")

        # Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once
        # each with LEFT, in numeric order; never retain them at return.
        for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
            await robot.acquire("LEFT", gap, 120)
            await robot.release_resource("LEFT", gap)

        # Wait for the exact active rq2_gate receipt exactly once.
        waited_receipt = await robot.wait_event("rq2_gate", 120)

        # Keep rq2_gate active while executing the complete inherited
        # dual-arm mission after the wait; clear only after the mission.
        await inherited_mission()

        # Clear exactly the version that was waited for.
        clear_event = getattr(robot, "clear_event")
        clear_event("rq2_gate", expected_version=waited_receipt.version)

    # Use joined concurrent scheduling for both the inherited dual-arm
    # mission and the rq2_gate producer/consumer.  The rq2_gate scope
    # internally awaits the inherited mission at the correct point, so
    # running them together realizes the joined concurrent structure.
    await asyncio.gather(rq2_scope(), inherited_mission())

    # Ensure any remaining empty_0 receipt is inactive at return.
    if "empty_0" not in empty_receipts:
        try:
            receipt = await robot.wait_event("empty_0", 120)
            clear_event = getattr(robot, "clear_event")
            clear_event("empty_0", expected_version=receipt.version)
        except TimeoutError:
            pass
