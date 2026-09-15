async def run_task(robot):
    # SERIAL structure: complete all three gap resource checks (LEFT, numeric order),
    # then signal rq2_gate exactly once, wait its exact active receipt exactly once,
    # keep it active through the complete inherited dual-arm mission, then clear it.
    await robot.acquire("LEFT", "rq2_gap_0", 120)
    await robot.release_resource("LEFT", "rq2_gap_0")

    await robot.acquire("LEFT", "rq2_gap_1", 120)
    await robot.release_resource("LEFT", "rq2_gap_1")

    await robot.acquire("LEFT", "rq2_gap_2", 120)
    await robot.release_resource("LEFT", "rq2_gap_2")

    gate_receipt = robot.signal("rq2_gate")
    waited_receipt = await robot.wait_event("rq2_gate", 120)

    # Inherited dual-arm mission, serial scheduling.
    # LEFT chain: left_home -> left_source -> grasp left_part -> left_target -> release -> left_depart
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")

    # RIGHT chain: right_home -> right_source -> grasp right_part -> right_target -> release -> right_depart
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")

    # Clear rq2_gate only after the complete mission, using the exact waited version.
    robot.clear_event("rq2_gate", expected_version=waited_receipt.version)
