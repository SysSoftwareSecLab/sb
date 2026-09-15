async def run_task(robot):
    # SERIAL structure: signal rq2_gate once, complete all three gap checks,
    # then wait rq2_gate once, keep it active through the dual-arm mission,
    # clear exactly that version after the mission.

    gate_receipt = robot.signal("rq2_gate")

    # Acquire/release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, numeric order.
    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 5)
        await robot.release_resource("LEFT", gap)

    # Wait for the exact active receipt of rq2_gate.
    waited_receipt = await robot.wait_event("rq2_gate", 5)

    # Inherited dual-arm mission, executed serially (LEFT chain then RIGHT chain).
    # LEFT chain: left_home -> left_source -> grasp left_part -> left_target -> release -> left_depart.
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")

    # RIGHT chain: right_home -> right_source -> grasp right_part -> right_target -> release -> right_depart.
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")

    # Clear rq2_gate only after the complete mission, using the waited receipt version.
    robot.clear_event("rq2_gate", expected_version=waited_receipt.version)
