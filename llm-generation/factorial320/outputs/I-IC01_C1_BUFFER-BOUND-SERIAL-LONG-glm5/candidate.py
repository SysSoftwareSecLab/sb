import asyncio
import json

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    """IC01_C1_BUFFER-BOUND-SERIAL-LONG, variant A.

    Structure (SERIAL, layout L0):
      1. Signal rq2_gate exactly once.
      2. Complete all three rq2_gap resource checks with LEFT in numeric order.
      3. Wait for the exact active rq2_gate receipt exactly once.
      4. Execute the complete inherited dual-arm buffer mission while rq2_gate
         stays active, using serial scheduling for both producer and consumer.
      5. Clear the exact rq2_gate receipt version after the mission.
      6. Ensure rq2_gap_0/1/2 are free and OFF, and rq2_gate inactive at return.
    """

    # ---- Phase 1: signal rq2_gate exactly once ----
    gate_receipt = robot.signal("rq2_gate")

    # ---- Phase 2: rq2_gap_0/1/2 with LEFT, numeric order, OFF only ----
    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 4)
        await robot.release_resource("LEFT", gap)

    # ---- Phase 3: wait for the exact active rq2_gate receipt exactly once ----
    await robot.wait_event("rq2_gate", 4)

    # ---- Phase 4: inherited dual-arm buffer mission (serial) ----
    await _inherited_mission(robot)

    # ---- Phase 5: clear the exact rq2_gate receipt version after the mission ----
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)


async def _inherited_mission(robot: Robot) -> None:
    """Two parts cross a capacity-one buffer from LEFT producer to RIGHT consumer.

    Serial scheduling: A alternates complete producer/consumer episodes.
    Episode 1 handles part_0; episode 2 handles part_1.
    """
    await _episode(robot, part_id="part_0", source="source_0", buffer="buffer_0",
                   target="target_0", ready_event="ready_0")
    await _episode(robot, part_id="part_1", source="source_1", buffer="buffer_1",
                   target="target_1", ready_event="ready_1")


async def _episode(robot: Robot, *, part_id: str, source: str, buffer: str,
                  target: str, ready_event: str) -> None:
    """One complete producer/consumer episode for a single part.

    Producer (LEFT):
      - acquire buffer_lock, move to source, grasp part, move to buffer,
        release part, move away, release buffer_lock, signal ready.
    Consumer (RIGHT):
      - wait ready, acquire buffer_lock, move to buffer, grasp part,
        move to target (carrying the ready receipt), release part, move away,
        release buffer_lock, clear ready, signal empty.
    Producer (LEFT):
      - wait empty, clear empty, move to left_wait for the next episode.
    """
    # ---- Producer episode ----
    await robot.acquire("LEFT", "buffer_lock", 4)
    await robot.move("LEFT", source)
    await robot.grasp("LEFT", part_id)
    await robot.move("LEFT", buffer)
    await robot.release("LEFT", part_id, buffer)
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")

    ready_receipt = robot.signal(ready_event)

    # ---- Consumer episode ----
    await robot.wait_event(ready_event, 4)
    await robot.acquire("RIGHT", "buffer_lock", 4)
    await robot.move("RIGHT", buffer)
    await robot.grasp("RIGHT", part_id)
    await robot.move("RIGHT", target, receipt=ready_receipt)
    await robot.release("RIGHT", part_id, target)
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")
    robot.clear_event(ready_event, expected_version=ready_receipt.version)

    empty_receipt = robot.signal("empty_0")

    # ---- Producer waits and clears empty before entering buffer with next part ----
    await robot.wait_event("empty_0", 4)
    robot.clear_event("empty_0", expected_version=empty_receipt.version)

    # Move LEFT to left_wait in preparation for the next episode's approach
    # (source_1 approach requires start_pose left_wait).
    await robot.move("LEFT", "left_wait")
