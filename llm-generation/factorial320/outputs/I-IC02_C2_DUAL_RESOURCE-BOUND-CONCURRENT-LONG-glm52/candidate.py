import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Shared gate receipt holder.
    gate_receipt_box: dict[str, object] = {}

    async def worker(arm: str, part: str, source: str, target: str,
                     home: str, depart: str) -> None:
        # Approach from home to source, then immediately grasp in the same
        # virtual moment (no intervening calls).
        await robot.move(arm, source)
        await robot.grasp(arm, part)

        # Carry the part to its target while owning both controllers.
        await robot.move(arm, target)

        # Release at the named support zone, then immediately depart.
        await robot.release(arm, part, target)
        await robot.move(arm, depart)

    async def left_worker() -> None:
        await worker("LEFT", "left_part", "left_source", "left_target",
                     "left_home", "left_depart")

    async def right_worker() -> None:
        await worker("RIGHT", "right_part", "right_source", "right_target",
                     "right_home", "right_depart")

    async def dual_arm_mission() -> None:
        # Inherited dual-resource mission: acquire fixture then tool, run both
        # workers concurrently, then release tool then fixture.
        await robot.acquire("LEFT", "fixture", 5)
        try:
            await robot.acquire("LEFT", "tool", 5)
            try:
                await asyncio.gather(left_worker(), right_worker())
            finally:
                await robot.release_resource("LEFT", "tool")
        finally:
            await robot.release_resource("LEFT", "fixture")

    async def gap_checks() -> None:
        # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with
        # LEFT in numeric order; never retain them at return.
        for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
            await robot.acquire("LEFT", rid, 5)
            try:
                pass
            finally:
                await robot.release_resource("LEFT", rid)

    async def gate_producer() -> None:
        # Signal rq2_gate exactly once and store the exact active receipt.
        receipt = robot.signal("rq2_gate")
        gate_receipt_box["receipt"] = receipt

    async def gate_consumer() -> None:
        # Wait for the exact active rq2_gate receipt exactly once, keep it
        # active through the protected scope, then clear that version after
        # the mission.
        receipt = await robot.wait_event("rq2_gate", 5)
        gate_receipt_box["waited"] = receipt
        try:
            await dual_arm_mission()
        finally:
            # Clear exactly the version we waited on, after the mission.
            robot.clear_event("rq2_gate", expected_version=receipt.version)

    # Joined concurrent scheduling for both the inherited dual-arm mission and
    # the rq2_gate producer/consumer. Signal rq2_gate, complete all three
    # rq2_gap resource checks, and only then wait for rq2_gate.
    await asyncio.gather(
        gate_producer(),
        gap_checks(),
        gate_consumer(),
    )
