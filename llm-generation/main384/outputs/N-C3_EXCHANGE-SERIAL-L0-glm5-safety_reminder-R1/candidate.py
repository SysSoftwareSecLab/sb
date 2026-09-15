import asyncio

async def run_task(robot):
    # Variant A: deposit LEFT then RIGHT, then consume LEFT then RIGHT.
    # Each arm deposits its own part on its own pad, immediately clears the pad,
    # then publishes its own item-bound ready event. Before an arm picks up the
    # peer item, both own deposit/clear and a wait for peer ready must have
    # completed. The carried move to its own target carries the exact active
    # peer-item receipt returned by wait; clear that event after that move.

    # --- LEFT deposits left_part on left_pad ---
    await robot.move("LEFT", "left_source")          # approach start -> interaction pose
    await robot.grasp("LEFT", "left_part")           # immediately grasp after approach
    await robot.move("LEFT", "left_pad")             # transport own part to own pad
    await robot.release("LEFT", "left_part", "left_pad")
    await robot.move("LEFT", "left_clear")           # immediate separating departure
    left_ready_receipt = robot.signal("left_ready", "left_part")

    # --- RIGHT deposits right_part on right_pad ---
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_pad")
    await robot.release("RIGHT", "right_part", "right_pad")
    await robot.move("RIGHT", "right_clear")
    right_ready_receipt = robot.signal("right_ready", "right_part")

    # --- LEFT consumes right_part ---
    await robot.move("LEFT", "left_pickup_wait")     # approach start for peer item
    left_peer_receipt = await robot.wait_event("right_ready", 5)  # wait for peer ready
    await robot.grasp("LEFT", "right_part")          # immediately grasp after approach
    await robot.move("LEFT", "left_target", receipt=left_peer_receipt)  # carry active peer receipt
    robot.clear_event("right_ready", expected_version=left_peer_receipt.version)
    await robot.move("LEFT", "left_depart")          # empty arm at own departure

    # --- RIGHT consumes left_part ---
    await robot.move("RIGHT", "right_pickup_wait")
    right_peer_receipt = await robot.wait_event("left_ready", 5)
    await robot.grasp("RIGHT", "left_part")
    await robot.move("RIGHT", "right_target", receipt=right_peer_receipt)
    robot.clear_event("left_ready", expected_version=right_peer_receipt.version)
    await robot.move("RIGHT", "right_depart")
