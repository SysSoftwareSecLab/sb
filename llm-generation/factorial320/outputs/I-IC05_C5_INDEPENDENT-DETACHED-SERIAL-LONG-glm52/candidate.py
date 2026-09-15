async def run_task(robot):
    # Phase 1: rq2_gate protocol (serial producer/consumer).
    # Signal rq2_gate exactly once.
    gate_receipt = robot.signal("rq2_gate")

    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT,
    # in numeric order; never retain them at return.
    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 5)
        await robot.release_resource("LEFT", gap)

    # Only now wait for the exact active receipt of rq2_gate exactly once.
    waited = await robot.wait_event("rq2_gate", 5)

    # Clear exactly that version after its assigned protected scope.
    robot.clear_event("rq2_gate", expected_version=waited.version)

    # Phase 2: inherited dual-arm mission, serial scheduling.
    # LEFT arm chain: left_home -> left_source -> grasp left_part ->
    # left_target -> release left_part -> left_depart.
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")

    # RIGHT arm chain: right_home -> right_source -> grasp right_part ->
    # right_target -> release right_part -> right_depart.
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
