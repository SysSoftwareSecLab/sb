import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    """IC03_C3_EXCHANGE-BOUND-CONCURRENT-SHORT, variant B.

    Joined concurrent scheduling of:
      * inherited dual-arm exchange (deposit own part, wait for peer ready,
        carry peer item to own target, clear peer ready after carrying move);
      * rq2_gate producer/consumer (acquire rq2_gap_0/1/2 with LEFT in order,
        signal rq2_gate, wait it, clear it after the mission).
    """

    # ---- shared gate coordination state ---------------------------------
    gate_receipt_box: dict[str, object] = {}
    gate_done = asyncio.Event()

    async def gap_checks() -> None:
        """Acquire and release rq2_gap_0/1/2 once each with LEFT, in order."""
        for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
            await robot.acquire("LEFT", rid, 5)
            await robot.release_resource("LEFT", rid)
        gate_done.set()

    async def gate_producer() -> None:
        """Signal rq2_gate exactly once after all gap checks complete."""
        await gate_done.wait()
        receipt = robot.signal("rq2_gate")
        gate_receipt_box["receipt"] = receipt

    async def gate_consumer() -> None:
        """Wait rq2_gate's exact active receipt once; clear after mission."""
        receipt = await robot.wait_event("rq2_gate", 30)
        gate_receipt_box["waited"] = receipt
        await mission_done.wait()
        clear_event_with_receipt(robot, receipt)

    # ---- inherited dual-arm exchange mission ----------------------------
    mission_done = asyncio.Event()

    async def left_worker() -> None:
        # Deposit own part on own pad, then clear the pad before publishing.
        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "left_pad")
        await robot.release("LEFT", "left_part", "left_pad")
        await robot.move("LEFT", "left_clear")
        robot.signal("left_ready")

        # Before picking up the peer item, wait for peer ready.
        right_receipt = await robot.wait_event("right_ready", 30)

        # Carry the exact active peer-item receipt to own target; clear after.
        await robot.move("LEFT", "left_pickup_wait", receipt=right_receipt)
        await robot.grasp("LEFT", "right_part")
        await robot.move("LEFT", "left_target")
        await robot.release("LEFT", "right_part", "left_target")
        await robot.move("LEFT", "left_depart")
        clear_event_with_receipt(robot, right_receipt)

    async def right_worker() -> None:
        # Deposit own part on own pad, then clear the pad before publishing.
        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", "right_source")
        await robot.grasp("RIGHT", "right_part")
        await robot.move("RIGHT", "right_pad")
        await robot.release("RIGHT", "right_part", "right_pad")
        await robot.move("RIGHT", "right_clear")
        robot.signal("right_ready")

        # Before picking up the peer item, wait for peer ready.
        left_receipt = await robot.wait_event("left_ready", 30)

        # Carry the exact active peer-item receipt to own target; clear after.
        await robot.move("RIGHT", "right_pickup_wait", receipt=left_receipt)
        await robot.grasp("RIGHT", "left_part")
        await robot.move("RIGHT", "right_target")
        await robot.release("RIGHT", "left_part", "right_target")
        await robot.move("RIGHT", "right_depart")
        clear_event_with_receipt(robot, left_receipt)

    async def inherited_mission() -> None:
        await asyncio.gather(left_worker(), right_worker())
        mission_done.set()

    # ---- joined concurrent scheduling -----------------------------------
    await asyncio.gather(
        gap_checks(),
        gate_producer(),
        gate_consumer(),
        inherited_mission(),
    )

    # ---- final cleanup of program-clearable ready events ----------------
    for event_id in ("left_ready", "right_ready"):
        receipt = await robot.wait_event(event_id, 5)
        clear_event_with_receipt(robot, receipt)


def clear_event_with_receipt(robot: Robot, receipt) -> None:
    """Clear an event using the version from an issued EventReceipt."""
    robot.clear_event(receipt.event_id, expected_version=receipt.version)
