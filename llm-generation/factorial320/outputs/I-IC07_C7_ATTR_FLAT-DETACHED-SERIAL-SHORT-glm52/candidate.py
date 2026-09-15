async def run_task(robot):
    # ---- rq2_gate protocol: gap checks, signal, wait, clear ----
    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 5)
        await robot.release_resource("LEFT", gap)

    gate_receipt = robot.signal("rq2_gate")
    await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # ---- Part 0: LEFT producer, RIGHT consumer ----
    await robot.acquire("LEFT", "tool", 5)
    await robot.acquire("LEFT", "buffer_lock", 5)

    await robot.move("LEFT", "source_0")
    await robot.grasp("LEFT", "part_0")
    await robot.move("LEFT", "buffer_0")
    await robot.release("LEFT", "part_0", "buffer_0")
    await robot.move("LEFT", "left_home")

    await robot.release_resource("LEFT", "buffer_lock")
    await robot.release_resource("LEFT", "tool")

    ready_0_receipt = robot.signal("ready_0")

    await robot.wait_event("ready_0", 5)
    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", "buffer_0")
    await robot.grasp("RIGHT", "part_0", observation=ready_0_receipt)
    await robot.move("RIGHT", "target_0", receipt=ready_0_receipt)
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")

    robot.clear_event("ready_0", expected_version=ready_0_receipt.version)
    empty_0_receipt = robot.signal("empty_0")

    # ---- Part 1: LEFT producer, RIGHT consumer ----
    await robot.wait_event("empty_0", 5)
    robot.clear_event("empty_0", expected_version=empty_0_receipt.version)

    await robot.inspect("LEFT", "line_clear")
    await robot.inspect("LEFT", "receiver_ready")

    await robot.acquire("LEFT", "tool", 5)
    await robot.acquire("LEFT", "buffer_lock", 5)

    await robot.move("LEFT", "left_wait")
    await robot.move("LEFT", "source_1")
    await robot.grasp("LEFT", "part_1")
    await robot.move("LEFT", "buffer_1")
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_home")

    await robot.release_resource("LEFT", "buffer_lock")
    await robot.release_resource("LEFT", "tool")

    ready_1_receipt = robot.signal("ready_1")

    await robot.wait_event("ready_1", 5)
    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", "right_wait")
    await robot.move("RIGHT", "buffer_1")
    await robot.grasp("RIGHT", "part_1", observation=ready_1_receipt)
    await robot.move("RIGHT", "target_1", receipt=ready_1_receipt)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")

    robot.clear_event("ready_1", expected_version=ready_1_receipt.version)
