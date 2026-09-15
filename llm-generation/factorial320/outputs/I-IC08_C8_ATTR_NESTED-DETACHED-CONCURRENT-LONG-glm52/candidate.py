import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- rq2_gate protocol (complete before inherited dual-arm mission) ----
    gate_receipt = robot.signal("rq2_gate")

    async def gap_check(idx: int) -> None:
        rid = f"rq2_gap_{idx}"
        await robot.acquire("LEFT", rid, 5)
        try:
            await robot.release_resource("LEFT", rid)
        finally:
            pass

    await asyncio.gather(
        gap_check(0),
        gap_check(1),
        gap_check(2),
    )

    waited = await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=waited.version)

    # ---- inherited dual-arm mission (joined concurrent producer/consumer) ----
    empty_receipt = robot.signal("empty_0")

    async def producer() -> None:
        # Episode 1: part_0
        await robot.acquire("LEFT", "tool", 5)
        try:
            await robot.move("LEFT", "source_0")
            await robot.grasp("LEFT", "part_0")
            await robot.acquire("LEFT", "buffer_lock", 5)
            try:
                await robot.move("LEFT", "buffer_0")
                await robot.release("LEFT", "part_0", "buffer_0")
                await robot.move("LEFT", "left_home")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")
        finally:
            await robot.release_resource("LEFT", "tool")

        robot.signal("ready_0")

        # Episode 2: part_1
        er = await robot.wait_event("empty_0", 10)
        robot.clear_event("empty_0", expected_version=er.version)

        # inspect both readiness facts, joined inside loop branch
        await asyncio.gather(
            robot.inspect("LEFT", "line_clear"),
            robot.inspect("LEFT", "receiver_ready"),
        )

        await robot.acquire("LEFT", "tool", 5)
        try:
            await robot.move("LEFT", "left_wait")
            await robot.move("LEFT", "source_1")
            await robot.grasp("LEFT", "part_1")
            await robot.acquire("LEFT", "buffer_lock", 5)
            try:
                await robot.move("LEFT", "buffer_1")
                await robot.release("LEFT", "part_1", "buffer_1")
                await robot.move("LEFT", "left_wait")
            finally:
                await robot.release_resource("LEFT", "buffer_lock")
        finally:
            await robot.release_resource("LEFT", "tool")

        robot.signal("ready_1")

    async def consumer() -> None:
        # Episode 1: part_0
        r0 = await robot.wait_event("ready_0", 10)
        await robot.acquire("RIGHT", "buffer_lock", 5)
        try:
            await robot.move("RIGHT", "buffer_0")
            await robot.grasp("RIGHT", "part_0")
            await robot.move("RIGHT", "target_0", receipt=r0)
            robot.clear_event("ready_0", expected_version=r0.version)
            await robot.release("RIGHT", "part_0", "target_0")
            await robot.move("RIGHT", "right_home")
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")

        robot.signal("empty_0")

        # Episode 2: part_1
        r1 = await robot.wait_event("ready_1", 10)
        await robot.acquire("RIGHT", "buffer_lock", 5)
        try:
            await robot.move("RIGHT", "right_wait")
            await robot.move("RIGHT", "buffer_1")
            await robot.grasp("RIGHT", "part_1")
            await robot.move("RIGHT", "target_1", receipt=r1)
            robot.clear_event("ready_1", expected_version=r1.version)
            await robot.release("RIGHT", "part_1", "target_1")
            await robot.move("RIGHT", "right_home")
        finally:
            await robot.release_resource("RIGHT", "buffer_lock")

    await asyncio.gather(producer(), consumer())
