import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- RQ2 gate protocol ----
    gate_receipt = robot.signal("rq2_gate")

    async def gap_check(idx: int) -> None:
        rid = f"rq2_gap_{idx}"
        await robot.acquire("LEFT", rid, 5)
        await robot.release_resource("LEFT", rid)

    await asyncio.gather(gap_check(0), gap_check(1), gap_check(2))

    waited = await robot.wait_event("rq2_gate", 5)
    if waited.version != gate_receipt.version:
        await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # ---- Inherited dual-arm buffer mission ----
    async def producer(part: str, src: str, buf: str, ready: str) -> None:
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", "left_home")
        await robot.grasp("LEFT", part)
        await robot.move("LEFT", buf, receipt=None)
        await robot.release("LEFT", part, buf)
        await robot.move("LEFT", "left_home")
        robot.signal(ready, part)
        await robot.release_resource("LEFT", "buffer_lock")

    async def consumer(part: str, buf: str, tgt: str, ready: str) -> None:
        rr = await robot.wait_event(ready, 10)
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.move("RIGHT", "right_home")
        await robot.grasp("RIGHT", part, observation=rr)
        await robot.move("RIGHT", tgt, receipt=rr)
        robot.clear_event(ready, expected_version=rr.version)
        await robot.release("RIGHT", part, tgt)
        await robot.move("RIGHT", "right_home")
        await robot.release_resource("RIGHT", "buffer_lock")
        robot.signal("empty_0", part)

    async def episode(part: str, src: str, buf: str, tgt: str, ready: str) -> None:
        p = asyncio.create_task(producer(part, src, buf, ready))
        c = asyncio.create_task(consumer(part, buf, tgt, ready))
        await p
        await c

    await episode("part_0", "source_0", "buffer_0", "target_0", "ready_0")

    er = await robot.wait_event("empty_0", 10)
    robot.clear_event("empty_0", expected_version=er.version)

    await robot.inspect("LEFT", "line_clear")
    await robot.refresh("LEFT", "line_clear")
    await robot.inspect("LEFT", "receiver_ready")
    await robot.refresh("LEFT", "receiver_ready")

    await episode("part_1", "source_1", "buffer_1", "target_1", "ready_1")
