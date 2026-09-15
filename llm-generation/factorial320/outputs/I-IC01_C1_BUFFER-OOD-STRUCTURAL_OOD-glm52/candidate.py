import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # IC01_C1_BUFFER-OOD-STRUCTURAL_OOD, variant A.
    # Required structural shape: FOR -> PAR_JOIN -> consumer IF.
    # The loop directly contains the join; the consumer IF guards the
    # complete inherited mission for the part produced in that iteration.

    async def producer(part: str, source: str, ready_event: str) -> None:
        # Producer: acquire buffer lock, enter buffer, place part, depart,
        # then publish ready. Both entry and departure own buffer_lock.
        await robot.acquire("LEFT", "buffer_lock", 120)
        try:
            await robot.move("LEFT", "left_home")
            await robot.move("LEFT", source)
            await robot.grasp("LEFT", part)
            await robot.move("LEFT", "left_home")
            await robot.move("LEFT", "buffer_0")
            await robot.release("LEFT", part, "buffer_0")
            await robot.move("LEFT", "left_home")
        finally:
            await robot.release_resource("LEFT", "buffer_lock")
        robot.signal(ready_event)

    async def consumer(part: str, ready_event: str, target: str) -> None:
        # Consumer: wait the exact active ready receipt, acquire lock, pick up
        # from buffer, carry to target using that receipt, clear ready after
        # the carried move, release on target, depart, then publish empty_0.
        receipt = await robot.wait_event(ready_event, 120)
        await robot.acquire("RIGHT", "buffer_lock", 120)
        try:
            await robot.move("RIGHT", "right_home")
            await robot.move("RIGHT", "buffer_0")
            await robot.grasp("RIGHT", part)
            await robot.move("RIGHT", target, receipt=receipt)
            clear_event = getattr(robot, "clear_event")
            clear_event(ready_event, expected_version=receipt.version)
            await robot.release("RIGHT", part, target)
            await robot.move("RIGHT", "right_home")
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")
        robot.signal("empty_0")

    # FOR: finite loop over the two parts.
    for part, source, ready_event, target in (
        ("part_0", "source_0", "ready_0", "target_0"),
        ("part_1", "source_1", "ready_1", "target_1"),
    ):
        # PAR_JOIN: concurrently join an rq2_gate producer and consumer.
        await asyncio.gather(
            producer(part, source, ready_event),
            consumer(part, ready_event, target),
        )

        # consumer IF: guard the complete mission for the next iteration.
        # For the second part, the producer must wait and clear empty_0
        # before entering the buffer again.
        if part == "part_0":
            empty_receipt = await robot.wait_event("empty_0", 120)
            clear_event = getattr(robot, "clear_event")
            clear_event("empty_0", expected_version=empty_receipt.version)

    # Ensure rq2_gate is inactive at return.
    clear_event = getattr(robot, "clear_event")
    clear_event("rq2_gate", expected_version=1)
