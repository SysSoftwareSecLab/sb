async def run_task(robot):
    """IC05_C5_INDEPENDENT-BOUND-CONCURRENT-SHORT, variant B.

    Concurrent fork/join of two independent release lifecycles plus an
    rq2_gate producer/consumer. rq2_gap_0..2 are acquired/released by LEFT
    in numeric order before signalling rq2_gate; the gate stays active for
    the complete dual-arm mission and is cleared only after that mission.
    """

    async def left_chain():
        await robot.move("LEFT", "left_home")
        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "left_target")
        await robot.release("LEFT", "left_part", "left_target")
        await robot.move("LEFT", "left_depart")

    async def right_chain():
        await robot.move("RIGHT", "right_home")
        await robot.move("RIGHT", "right_source")
        await robot.grasp("RIGHT", "right_part")
        await robot.move("RIGHT", "right_target")
        await robot.release("RIGHT", "right_part", "right_target")
        await robot.move("RIGHT", "right_depart")

    async def gap_checks():
        await robot.acquire("LEFT", "rq2_gap_0", 5)
        await robot.release_resource("LEFT", "rq2_gap_0")
        await robot.acquire("LEFT", "rq2_gap_1", 5)
        await robot.release_resource("LEFT", "rq2_gap_1")
        await robot.acquire("LEFT", "rq2_gap_2", 5)
        await robot.release_resource("LEFT", "rq2_gap_2")

    import asyncio

    gap_task = asyncio.create_task(gap_checks())
    await gap_task

    receipt = robot.signal("rq2_gate")
    await robot.wait_event("rq2_gate", 5)

    left_task = asyncio.create_task(left_chain())
    right_task = asyncio.create_task(right_chain())
    await asyncio.gather(left_task, right_task)

    robot.clear_event("rq2_gate", expected_version=receipt.version)
