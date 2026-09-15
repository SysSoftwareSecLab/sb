import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Shared coordination state.
    state = {
        "ready_0_receipt": None,
        "ready_1_receipt": None,
        "empty_0_receipt": None,
        "rq2_gate_receipt": None,
    }

    async def producer_episode(part: str, source: str, buffer: str,
                               ready_event: str, start_pose: str) -> None:
        """LEFT: acquire tool, pick part from source, place at buffer, depart,
        publish ready, then wait for empty and clear it."""
        await robot.acquire("LEFT", "tool", 120)
        await robot.move("LEFT", start_pose, 4)
        await robot.move("LEFT", source, 4)
        await robot.grasp("LEFT", part)
        await robot.move("LEFT", "left_home", 4)

        # Enter buffer: own lock for entry and departure.
        await robot.acquire("LEFT", "buffer_lock", 120)
        await robot.move("LEFT", buffer, 4)
        await robot.release("LEFT", part, buffer)
        # Immediate separating departure from buffer.
        await robot.move("LEFT", "left_home", 4)
        await robot.release_resource("LEFT", "buffer_lock")

        # Publish ready after departing buffer.
        state[ready_event + "_receipt"] = robot.signal(ready_event, part)

        # Wait for consumer to publish empty_0, then clear it before next entry.
        er = await robot.wait_event("empty_0", 120)
        robot.clear_event("empty_0", expected_version=er.version)
        state["empty_0_receipt"] = None

        await robot.release_resource("LEFT", "tool")

    async def consumer_episode(part: str, buffer: str, target: str,
                               ready_event: str, start_pose: str) -> None:
        """RIGHT: wait ready, acquire lock, pick from buffer, carry to target
        using ready receipt, release, depart, publish empty_0."""
        rr = await robot.wait_event(ready_event, 120)
        state[ready_event + "_receipt"] = rr

        await robot.acquire("RIGHT", "buffer_lock", 120)
        await robot.move("RIGHT", start_pose, 4)
        await robot.move("RIGHT", buffer, 4)
        await robot.grasp("RIGHT", part)

        # Carried move to target supplies the exact active item receipt.
        await robot.move("RIGHT", target, 4, receipt=rr)

        # Clear ready after carried move completes.
        robot.clear_event(ready_event, expected_version=rr.version)
        state[ready_event + "_receipt"] = None

        await robot.release("RIGHT", part, target)
        # Immediate separating departure from target.
        await robot.move("RIGHT", "right_home", 4)
        await robot.release_resource("RIGHT", "buffer_lock")

        # Publish empty_0 after departing target.
        state["empty_0_receipt"] = robot.signal("empty_0", part)

    async def inherited_mission() -> None:
        """A alternates complete producer/consumer episodes; B runs producer and
        consumer coroutines together for each item."""
        # Item 0: LEFT produces while RIGHT consumes concurrently.
        p0 = asyncio.create_task(
            producer_episode("part_0", "source_0", "buffer_0",
                             "ready_0", "left_home")
        )
        c0 = asyncio.create_task(
            consumer_episode("part_0", "buffer_0", "target_0",
                             "ready_0", "right_home")
        )
        await p0
        await c0

        # Item 1: wait and clear empty_0 already done by producer_episode;
        # inspect both readiness facts serially inside the loop branch.
        await robot.inspect("LEFT", "line_clear")
        await robot.inspect("LEFT", "receiver_ready")

        p1 = asyncio.create_task(
            producer_episode("part_1", "source_1", "buffer_1",
                             "ready_1", "left_wait")
        )
        c1 = asyncio.create_task(
            consumer_episode("part_1", "buffer_1", "target_1",
                             "ready_1", "right_wait")
        )
        await p1
        await c1

    async def rq2_scope() -> None:
        """Signal rq2_gate, complete three gap resource checks, wait gate,
        keep active through inherited mission, clear after mission."""
        state["rq2_gate_receipt"] = robot.signal("rq2_gate")

        for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
            await robot.acquire("LEFT", gap, 120)
            await robot.release_resource("LEFT", gap)

        gr = await robot.wait_event("rq2_gate", 120)
        state["rq2_gate_receipt"] = gr

        await inherited_mission()

        robot.clear_event("rq2_gate", expected_version=gr.version)
        state["rq2_gate_receipt"] = None

    await rq2_scope()
