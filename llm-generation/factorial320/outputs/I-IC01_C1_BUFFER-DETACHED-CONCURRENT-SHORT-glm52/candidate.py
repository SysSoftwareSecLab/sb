import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Shared coordination state.
    state = {
        "empty_receipt": None,   # active empty_0 receipt for producer's second-entry gate
        "ready_receipts": {},    # part_id -> active ready receipt for consumer carried move
        "rq2_gate_receipt": None,
    }

    async def rq2_gap_protocol() -> None:
        """Acquire/release rq2_gap_0..2 with LEFT in numeric order, then gate protocol."""
        for i in range(3):
            rid = f"rq2_gap_{i}"
            await robot.acquire("LEFT", rid, 10)
            await robot.release_resource("LEFT", rid)
        # All three gap checks complete; signal gate, wait immediately, clear after scope.
        rc = robot.signal("rq2_gate")
        state["rq2_gate_receipt"] = rc
        waited = await robot.wait_event("rq2_gate", 10)
        assert waited.version == rc.version
        # Protected scope is the gate protocol itself; clear before inherited mission.
        robot.clear_event("rq2_gate", expected_version=rc.version)

    async def producer_episode(part_id: str, source_pose: str, buffer_pose: str,
                               ready_event: str) -> None:
        """LEFT: pick part from source, place at buffer, depart, publish ready."""
        await robot.move("LEFT", source_pose)
        await robot.grasp("LEFT", part_id)
        await robot.acquire("LEFT", "buffer_lock", 10)
        await robot.move("LEFT", buffer_pose, receipt=state["empty_receipt"])
        await robot.release("LEFT", part_id, buffer_pose)
        await robot.move("LEFT", "left_home")
        await robot.release_resource("LEFT", "buffer_lock")
        # Departed before publishing ready.
        rc = robot.signal(ready_event, item_id=part_id)
        state["ready_receipts"][part_id] = rc

    async def consumer_episode(part_id: str, buffer_pose: str, start_pose: str,
                               target_pose: str, ready_event: str) -> None:
        """RIGHT: wait ready, enter buffer, pickup, carry to target, clear ready, depart, empty."""
        rc = await robot.wait_event(ready_event, 30)
        assert rc.item_id == part_id
        await robot.acquire("RIGHT", "buffer_lock", 10)
        await robot.move("RIGHT", start_pose)
        await robot.grasp("RIGHT", part_id, observation=rc)
        await robot.move("RIGHT", target_pose, receipt=rc)
        # Consumer clears ready after its carried move.
        robot.clear_event(ready_event, expected_version=rc.version)
        await robot.release("RIGHT", part_id, target_pose)
        await robot.move("RIGHT", "right_home")
        await robot.release_resource("RIGHT", "buffer_lock")
        # Departed before publishing empty_0.
        if part_id == "part_0":
            erc = robot.signal("empty_0", item_id=part_id)
            state["empty_receipt"] = erc

    async def dual_arm_mission() -> None:
        """Inherited capacity-one buffer mission with joined concurrent scheduling."""
        # Episode 1: part_0 source_0 -> buffer_0 -> target_0.
        p0 = asyncio.create_task(producer_episode("part_0", "source_0", "buffer_0", "ready_0"))
        c0 = asyncio.create_task(consumer_episode("part_0", "buffer_0", "right_home",
                                                  "target_0", "ready_0"))
        await p0
        await c0
        # Producer waits and clears empty_0 before entering buffer with second part.
        erc = await robot.wait_event("empty_0", 30)
        robot.clear_event("empty_0", expected_version=erc.version)
        # Episode 2: part_1 source_1 -> buffer_1 -> target_1.
        p1 = asyncio.create_task(producer_episode("part_1", "source_1", "buffer_1", "ready_1"))
        c1 = asyncio.create_task(consumer_episode("part_1", "buffer_1", "right_wait",
                                                  "target_1", "ready_1"))
        await p1
        await c1

    # Complete rq2_gate protocol before starting the complete inherited dual-arm mission.
    await rq2_gap_protocol()
    # Use joined concurrent scheduling for both the inherited dual-arm mission and the
    # rq2_gate producer/consumer (gate already completed/cleared above).
    await dual_arm_mission()
