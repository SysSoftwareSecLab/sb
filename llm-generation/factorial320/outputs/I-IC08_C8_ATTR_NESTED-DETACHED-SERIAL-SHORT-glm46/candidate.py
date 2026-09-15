import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- RQ2 Gap Resource Protocol ---
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order.
    # Complete all three checks before signalling rq2_gate.
    # Then signal rq2_gate, wait immediately after, and clear exactly that version.
    
    gap_resources = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    for res_id in gap_resources:
        await robot.acquire("LEFT", res_id, timeout_s=4.0)
        await robot.release_resource("LEFT", res_id)
    
    gate_receipt = robot.signal("rq2_gate")
    await robot.wait_event("rq2_gate", timeout_s=4.0)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- Inherited Dual-Arm Mission (Serial Schedule) ---
    # LEFT is Producer, RIGHT is Consumer.
    # Items: part_0, part_1.
    # Buffer: buffer_0 (for part_0), buffer_1 (for part_1).
    # Events: ready_0, ready_1, empty_0.
    # Resources: buffer_lock, tool.
    
    # Helper for Producer Episode
    async def producer_episode(item_id: str, source_pose: str, buffer_pose: str, ready_event_id: str, wait_empty: bool):
        # 1. Wait and clear empty_0 if required (for item 1)
        if wait_empty:
            await robot.wait_event("empty_0", timeout_s=4.0)
            # empty_0 initial version is 0. Assuming it was signaled once by consumer.
            robot.clear_event("empty_0", expected_version=1)

        # 2. Acquire tool and buffer_lock
        await robot.acquire("LEFT", "tool", timeout_s=4.0)
        await robot.acquire("LEFT", "buffer_lock", timeout_s=4.0)

        # 3. Move to source, grasp, move to buffer
        await robot.move("LEFT", source_pose)
        await robot.grasp("LEFT", item_id)
        await robot.move("LEFT", buffer_pose)

        # 4. Release at buffer and depart immediately
        await robot.release("LEFT", item_id, buffer_pose)
        # Depart: Move to left_wait (for part_1) or left_home (for part_0)
        # Task says "immediately departs before ready publication".
        # For part_0, next is left_home. For part_1, next is left_wait.
        depart_pose = "left_wait" if item_id == "part_1" else "left_home"
        await robot.move("LEFT", depart_pose)

        # 5. Release resources and signal ready
        await robot.release_resource("LEFT", "buffer_lock")
        await robot.release_resource("LEFT", "tool")
        robot.signal(ready_event_id)

    # Helper for Consumer Episode
    async def consumer_episode(item_id: str, buffer_pose: str, target_pose: str, ready_event_id: str, inspect_facts: bool):
        # 1. Wait for ready event
        ready_receipt = await robot.wait_event(ready_event_id, timeout_s=4.0)

        # 2. Acquire buffer_lock and tool
        await robot.acquire("RIGHT", "buffer_lock", timeout_s=4.0)
        await robot.acquire("RIGHT", "tool", timeout_s=4.0)

        # 3. Move to buffer, grasp
        await robot.move("RIGHT", buffer_pose)
        await robot.grasp("RIGHT", item_id)

        # 4. Depart buffer (release lock) and move to target
        # "Consumer waits the corresponding ready receipt before pickup, and supplies that exact active item receipt on carried move to target."
        # "Consumer clears ready after its carried move"
        # "Both participants own buffer_lock during buffer entry and departure."
        # Departure move: right_wait -> target
        await robot.release_resource("RIGHT", "buffer_lock")
        await robot.move("RIGHT", target_pose, receipt=ready_receipt)

        # 5. Clear ready event
        robot.clear_event(ready_event_id, expected_version=ready_receipt.version)

        # 6. Release at target and depart immediately
        await robot.release("RIGHT", item_id, target_pose)
        await robot.move("RIGHT", "right_home")

        # 7. Release tool
        await robot.release_resource("RIGHT", "tool")

        # 8. Signal empty_0
        robot.signal("empty_0")

    # --- Execution Flow ---
    
    # Episode 1: part_0
    # Producer: source_0 -> buffer_0. No wait for empty. Signal ready_0.
    await producer_episode("part_0", "source_0", "buffer_0", "ready_0", wait_empty=False)
    
    # Consumer: buffer_0 -> target_0. Wait ready_0. Signal empty_0.
    await consumer_episode("part_0", "buffer_0", "target_0", "ready_0", inspect_facts=False)

    # Episode 2: part_1
    # Producer: source_1 -> buffer_1. Wait empty_0. Signal ready_1.
    # "For item 1, wait and clear empty_0, then inspect both readiness facts"
    # The inspection happens inside the producer logic before signaling ready_1?
    # Task: "Producer waits and clears empty_0 before entering buffer with the second part."
    # Task: "For item 1, wait and clear empty_0, then inspect both readiness facts"
    # This implies the inspection is part of the Producer's responsibility for item 1.
    # We need to modify producer_episode or handle inspection here.
    # Let's handle the specific logic for part_1 here to satisfy the inspection requirement.
    
    # Wait and clear empty_0 (version 1, signaled by consumer of part_0)
    await robot.wait_event("empty_0", timeout_s=4.0)
    robot.clear_event("empty_0", expected_version=1)
    
    # Inspect both readiness facts (line_clear, receiver_ready)
    # "C8 joins the two checks inside the loop branch" -> asyncio.gather
    obs1 = robot.inspect("LEFT", "line_clear")
    obs2 = robot.inspect("LEFT", "receiver_ready")
    await asyncio.gather(obs1, obs2)
    
    # Continue with Producer Episode for part_1
    # Acquire tool, lock, move, grasp, move, release, depart, release, signal
    await robot.acquire("LEFT", "tool", timeout_s=4.0)
    await robot.acquire("LEFT", "buffer_lock", timeout_s=4.0)
    await robot.move("LEFT", "source_1")
    await robot.grasp("LEFT", "part_1")
    await robot.move("LEFT", "buffer_1")
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_home") # Depart to home
    await robot.release_resource("LEFT", "buffer_lock")
    await robot.release_resource("LEFT", "tool")
    robot.signal("ready_1")

    # Consumer Episode for part_1
    # Wait ready_1, acquire, move, grasp, depart, move (receipt), clear, release, depart, release, signal empty
    ready_receipt_1 = await robot.wait_event("ready_1", timeout_s=4.0)
    await robot.acquire("RIGHT", "buffer_lock", timeout_s=4.0)
    await robot.acquire("RIGHT", "tool", timeout_s=4.0)
    await robot.move("RIGHT", "buffer_1")
    await robot.grasp("RIGHT", "part_1")
    await robot.release_resource("RIGHT", "buffer_lock")
    await robot.move("RIGHT", "target_1", receipt=ready_receipt_1)
    robot.clear_event("ready_1", expected_version=ready_receipt_1.version)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "tool")
    robot.signal("empty_0")

    # Final state check implicit in completion.
    # rq2_gate inactive (cleared).
    # rq2_gap resources free (released).
    # Arms at homes.
    # Parts at targets.
    # Buffer empty.
    # Lock free.
