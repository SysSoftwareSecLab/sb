import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # IC01_C1_BUFFER-OOD-DEVELOPMENT_SHAPE, variant A, SERIAL/L0.
    # Required development shape: FOR -> IF -> PAR_JOIN.
    # The IF contains the join; the consumer has no mission guard.

    items = ["part_0", "part_1"]
    source_poses = {"part_0": "source_0", "part_1": "source_1"}
    buffer_poses = {"part_0": "buffer_0", "part_1": "buffer_1"}
    target_poses = {"part_0": "target_0", "part_1": "target_1"}
    ready_events = {"part_0": "ready_0", "part_1": "ready_1"}

    async def producer(part: str) -> None:
        # Acquire buffer lock, enter buffer, place part, depart, publish ready.
        await robot.acquire("LEFT", "buffer_lock", 10)

        await robot.move("LEFT", "left_home", 4)
        await robot.move("LEFT", source_poses[part], 4)
        await robot.grasp("LEFT", part)
        await robot.move("LEFT", "left_home", 4)
        await robot.move("LEFT", "left_wait", 4)
        await robot.move("LEFT", buffer_poses[part], 4)
        await robot.release("LEFT", part, buffer_poses[part])
        await robot.move("LEFT", "left_wait", 4)
        await robot.move("LEFT", "left_home", 4)

        robot.signal(ready_events[part])
        await robot.release_resource("LEFT", "buffer_lock")

    async def consumer(part: str) -> None:
        # Wait exact active ready receipt, carry to target using that receipt,
        # clear ready after carried move, release on target, depart, publish empty.
        ready_receipt = await robot.wait_event(ready_events[part], 10)

        await robot.acquire("RIGHT", "buffer_lock", 10)

        await robot.move("RIGHT", "right_home", 4)
        await robot.move("RIGHT", "right_wait", 4)
        await robot.move("RIGHT", buffer_poses[part], 4)
        await robot.grasp("RIGHT", part)
        await robot.move("RIGHT", "right_wait", 4, receipt=ready_receipt)
        await robot.move("RIGHT", "target_0", 4, receipt=ready_receipt) if part == "part_0" else await robot.move("RIGHT", "target_1", 4, receipt=ready_receipt)

        clear_event = getattr(robot, "clear_event")
        clear_event(ready_events[part], expected_version=ready_receipt.version)

        await robot.release("RIGHT", part, target_poses[part])
        await robot.move("RIGHT", "right_wait", 4)
        await robot.move("RIGHT", "right_home", 4)

        robot.signal("empty_0")
        await robot.release_resource("RIGHT", "buffer_lock")

    for part in items:
        # FOR loop body: IF contains the PAR_JOIN.
        if True:
            await asyncio.gather(producer(part), consumer(part))

        # Producer waits and clears empty_0 before entering buffer with next part.
        empty_receipt = await robot.wait_event("empty_0", 10)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

    # rq2_gate inactive at return: it was never signaled, so it is inactive.
    return
