import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- shared gate coordination ----
    gate_signaled = asyncio.Event()
    gate_receipt_holder: dict[str, object] = {}
    gaps_done = asyncio.Event()

    # ---- inherited dual-arm mission coordination ----
    empty_for_second = asyncio.Event()
    empty_for_second.set()  # first producer may enter immediately
    second_producer_done = asyncio.Event()

    async def rq2_gap_checks() -> None:
        """Signal rq2_gate, acquire/release rq2_gap_0..2 in order, then wait gate."""
        receipt = robot.signal("rq2_gate")
        gate_receipt_holder["receipt"] = receipt
        gate_signaled.set()

        for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
            await robot.acquire("LEFT", rid, 10)
            await robot.release_resource("LEFT", rid)

        gaps_done.set()
        waited = await robot.wait_event("rq2_gate", 10)
        gate_receipt_holder["waited"] = waited

    async def inherited_mission() -> None:
        """Producer/consumer episodes for part_0 then part_1 over capacity-one buffer."""
        await produce_part0()
        await consume_part0()
        await produce_part1()
        await consume_part1()

    async def produce_part0() -> None:
        await robot.acquire("LEFT", "buffer_lock", 10)
        await robot.move("LEFT", "left_home")
        await robot.grasp("LEFT", "part_0")
        await robot.move("LEFT", "buffer_0", receipt=None)
        await robot.release("LEFT", "part_0", "buffer_0")
        await robot.move("LEFT", "left_home")
        await robot.release_resource("LEFT", "buffer_lock")
        robot.signal("ready_0")

    async def consume_part0() -> None:
        ready_receipt = await robot.wait_event("ready_0", 10)
        await robot.acquire("RIGHT", "buffer_lock", 10)
        await robot.move("RIGHT", "right_home")
        await robot.grasp("RIGHT", "part_0")
        await robot.move("RIGHT", "target_0", receipt=ready_receipt)
        robot.clear_event("ready_0", expected_version=ready_receipt.version)
        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_home")
        await robot.release_resource("RIGHT", "buffer_lock")
        robot.signal("empty_0")

    async def produce_part1() -> None:
        await empty_for_second.wait()
        empty_receipt = await robot.wait_event("empty_0", 10)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

        await robot.acquire("LEFT", "buffer_lock", 10)
        await robot.move("LEFT", "left_wait")
        await robot.grasp("LEFT", "part_1")
        await robot.move("LEFT", "buffer_1", receipt=None)
        await robot.release("LEFT", "part_1", "buffer_1")
        await robot.move("LEFT", "left_home")
        await robot.release_resource("LEFT", "buffer_lock")
        robot.signal("ready_1")
        second_producer_done.set()

    async def consume_part1() -> None:
        ready_receipt = await robot.wait_event("ready_1", 10)
        await robot.acquire("RIGHT", "buffer_lock", 10)
        await robot.move("RIGHT", "right_wait")
        await robot.grasp("RIGHT", "part_1")
        await robot.move("RIGHT", "target_1", receipt=ready_receipt)
        robot.clear_event("ready_1", expected_version=ready_receipt.version)
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home")
        await robot.release_resource("RIGHT", "buffer_lock")

    async def gate_scope() -> None:
        """Keep rq2_gate active across the complete inherited dual-arm mission."""
        await gaps_done.wait()
        await inherited_mission()
        waited = gate_receipt_holder["waited"]
        robot.clear_event("rq2_gate", expected_version=waited.version)

    await asyncio.gather(
        rq2_gap_checks(),
        gate_scope(),
    )
