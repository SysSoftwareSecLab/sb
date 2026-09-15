import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Shared gate receipt for the protected dual-arm mission.
    gate_receipt = {"version": None}

    async def gap_checks() -> None:
        """Acquire rq2_gap_0/1/2 once each with LEFT in numeric order, then release."""
        for name in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
            await robot.acquire("LEFT", name, 5)
            try:
                await robot.release_resource("LEFT", name)
            except BaseException:
                try:
                    await robot.release_resource("LEFT", name)
                except BaseException:
                    pass
                raise

    async def worker(arm: str, part: str, source: str, target: str,
                     home: str, depart: str) -> None:
        """Carry one part to its target while owning fixture and tool, then depart."""
        await robot.acquire(arm, "fixture", 5)
        try:
            await robot.acquire(arm, "tool", 5)
            try:
                # Approach from declared start_pose to the part's current support.
                await robot.move(arm, source)
                await robot.grasp(arm, part)
                # Transport to target and release onto the named support zone.
                await robot.move(arm, target)
                await robot.release(arm, part, target)
                # Immediate separating departure from the release pose.
                await robot.move(arm, depart)
            finally:
                try:
                    await robot.release_resource(arm, "tool")
                except BaseException:
                    pass
        finally:
            try:
                await robot.release_resource(arm, "fixture")
            except BaseException:
                pass

    async def left_worker() -> None:
        await worker("LEFT", "left_part", "left_source", "left_target",
                     "left_home", "left_depart")

    async def right_worker() -> None:
        await worker("RIGHT", "right_part", "right_source", "right_target",
                     "right_home", "right_depart")

    async def protected_mission() -> None:
        """Inherited dual-arm mission, executed serially while gate is active."""
        await left_worker()
        await right_worker()

    # Complete all three gap resource checks before signalling the gate.
    await gap_checks()

    # Signal rq2_gate exactly once.
    receipt = robot.signal("rq2_gate")
    gate_receipt["version"] = receipt.version

    try:
        # Wait the exact active receipt exactly once, immediately after signal.
        await robot.wait_event("rq2_gate", 5)
        # Keep gate active while executing the complete inherited mission.
        await protected_mission()
    finally:
        # Clear exactly that version after the assigned protected scope.
        if gate_receipt["version"] is not None:
            try:
                robot.clear_event("rq2_gate", expected_version=gate_receipt["version"])
            except BaseException:
                pass
