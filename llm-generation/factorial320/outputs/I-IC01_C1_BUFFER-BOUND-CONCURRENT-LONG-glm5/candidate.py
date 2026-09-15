import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- Shared state ----
    empty_0_receipt = {"version": None}
    ready_0_receipt = {"version": None}
    ready_1_receipt = {"version": None}
    gate_receipt = {"version": None}

    # ---- LEFT producer: place part_0 at buffer_0, depart, signal ready_0 ----
    async def producer_part_0() -> None:
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", "left_home", 5)
        await robot.grasp("LEFT", "part_0")
        await robot.move("LEFT", "buffer_0", 5)
        await robot.release("LEFT", "part_0", "buffer_0")
        await robot.move("LEFT", "left_home", 5)
        await robot.release_resource("LEFT", "buffer_lock")
        r = robot.signal("ready_0", "part_0")
        ready_0_receipt["version"] = r.version

    # ---- RIGHT consumer: wait ready_0, pickup part_0, carry to target_0,
    # clear ready_0, release, depart, signal empty_0 ----
    async def consumer_part_0() -> None:
        r = await robot.wait_event("ready_0", 30)
        ready_0_receipt["version"] = r.version
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.move("RIGHT", "right_home", 5)
        await robot.grasp("RIGHT", "part_0")
        await robot.move("RIGHT", "target_0", 5, receipt=r)
        robot.clear_event("ready_0", expected_version=r.version)
        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_home", 5)
        await robot.release_resource("RIGHT", "buffer_lock")
        e = robot.signal("empty_0", "part_0")
        empty_0_receipt["version"] = e.version

    # ---- LEFT producer: wait empty_0, clear it, place part_1 at buffer_1,
    # depart, signal ready_1 ----
    async def producer_part_1() -> None:
        e = await robot.wait_event("empty_0", 30)
        empty_0_receipt["version"] = e.version
        robot.clear_event("empty_0", expected_version=e.version)
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", "left_home", 5)
        await robot.move("LEFT", "left_wait", 5)
        await robot.grasp("LEFT", "part_1")
        await robot.move("LEFT", "buffer_1", 5)
        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.move("LEFT", "left_wait", 5)
        await robot.move("LEFT", "left_home", 5)
        await robot.release_resource("LEFT", "buffer_lock")
        r = robot.signal("ready_1", "part_1")
        ready_1_receipt["version"] = r.version

    # ---- RIGHT consumer: wait ready_1, pickup part_1, carry to target_1,
    # clear ready_1, release, depart ----
    async def consumer_part_1() -> None:
        r = await robot.wait_event("ready_1", 30)
        ready_1_receipt["version"] = r.version
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.move("RIGHT", "right_home", 5)
        await robot.move("RIGHT", "right_wait", 5)
        await robot.grasp("RIGHT", "part_1")
        await robot.move("RIGHT", "target_1", 5, receipt=r)
        robot.clear_event("ready_1", expected_version=r.version)
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_wait", 5)
        await robot.move("RIGHT", "right_home", 5)
        await robot.release_resource("RIGHT", "buffer_lock")

    # ---- rq2_gap resource checks with LEFT in numeric order ----
    async def gap_checks() -> None:
        await robot.acquire("LEFT", "rq2_gap_0", 5)
        await robot.release_resource("LEFT", "rq2_gap_0")
        await robot.acquire("LEFT", "rq2_gap_1", 5)
        await robot.release_resource("LEFT", "rq2_gap_1")
        await robot.acquire("LEFT", "rq2_gap_2", 5)
        await robot.release_resource("LEFT", "rq2_gap_2")

    # ---- Signal rq2_gate, run gap checks, then wait gate, then run
    # inherited dual-arm mission, then clear gate ----
    async def gate_scope() -> None:
        g = robot.signal("rq2_gate")
        gate_receipt["version"] = g.version
        await asyncio.gather(gap_checks())
        gw = await robot.wait_event("rq2_gate", 30)
        gate_receipt["version"] = gw.version
        await asyncio.gather(
            producer_part_0(),
            consumer_part_0(),
            producer_part_1(),
            consumer_part_1(),
        )
        robot.clear_event("rq2_gate", expected_version=gw.version)

    await gate_scope()
