import asyncio
from bridge_robot_api import MotionFault

async def run_task(robot):
    # ---- helpers ----
    async def acquire_lock(arm, resource_id, timeout_s=4):
        return await robot.acquire(arm, resource_id, timeout_s)

    async def producer_episode(part, source, buffer, ready_event, left_wait, right_wait):
        # LEFT owns tool from before each source pickup through ready publication
        await acquire_lock("LEFT", "tool", 4)
        try:
            # approach source from left_home, then immediately grasp
            await robot.move("LEFT", source, 4)
            await robot.grasp("LEFT", part)
            # move to buffer (LEFT carries part)
            await robot.move("LEFT", buffer, 4)
            # buffer entry: own buffer_lock
            await acquire_lock("LEFT", "buffer_lock", 4)
            try:
                # release part at buffer
                await robot.release("LEFT", part, buffer)
                # immediate departure from buffer
                await robot.move("LEFT", left_wait, 4)
            finally:
                await robot.set_mode("LEFT", "buffer_lock", "OFF")
                await robot.release_resource("LEFT", "buffer_lock")
            # publish ready after departure
            ready_receipt = robot.signal(ready_event, part)
            # LEFT releases tool on every exit
            await robot.set_mode("LEFT", "tool", "OFF")
            await robot.release_resource("LEFT", "tool")
            return ready_receipt
        except BaseException:
            # best-effort tool release on error
            try:
                await robot.set_mode("LEFT", "tool", "OFF")
                await robot.release_resource("LEFT", "tool")
            except Exception:
                pass
            raise

    async def consumer_episode(part, buffer, target, ready_receipt, right_wait):
        # wait corresponding ready receipt before pickup
        waited = await robot.wait_event(ready_receipt.event_id, 4)
        # RIGHT owns buffer_lock during buffer entry
        await acquire_lock("RIGHT", "buffer_lock", 4)
        try:
            # approach buffer from right_home, then immediately grasp
            await robot.move("RIGHT", buffer, 4)
            await robot.grasp("RIGHT", part, observation=waited)
            # immediate departure from buffer
            await robot.move("RIGHT", right_wait, 4)
        finally:
            await robot.set_mode("RIGHT", "buffer_lock", "OFF")
            await robot.release_resource("RIGHT", "buffer_lock")
        # carried move to target using exact active item receipt
        await robot.move("RIGHT", target, 4, receipt=waited)
        # clear ready after carried move
        robot.clear_event(ready_receipt.event_id, expected_version=ready_receipt.version)
        # release on target and depart before publishing empty_0
        await robot.release("RIGHT", part, target)
        await robot.move("RIGHT", "right_home", 4)
        # publish empty
        empty_receipt = robot.signal("empty_0", part)
        return empty_receipt

    async def producer_wait_empty_and_inspect():
        # wait and clear empty_0 before entering buffer with second part
        empty_receipt = await robot.wait_event("empty_0", 4)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)
        # inspect both readiness facts serially
        await robot.inspect("LEFT", "line_clear")
        await robot.inspect("LEFT", "receiver_ready")

    # ---- Episode 0: part_0 ----
    ready0 = await producer_episode(
        "part_0", "source_0", "buffer_0", "ready_0", "left_wait", "right_wait"
    )
    empty0 = await consumer_episode(
        "part_0", "buffer_0", "target_0", ready0, "right_wait"
    )
    # Producer waits and clears empty_0 before entering buffer with the second part
    robot.clear_event("empty_0", expected_version=empty0.version)

    # ---- Episode 1: part_1 ----
    ready1 = await producer_episode(
        "part_1", "source_1", "buffer_1", "ready_1", "left_wait", "right_wait"
    )
    await consumer_episode(
        "part_1", "buffer_1", "target_1", ready1, "right_wait"
    )

    # ---- rq2_gate protected scope ----
    gate_receipt = robot.signal("rq2_gate")
    # complete all three rq2_gap resource checks, then wait for rq2_gate
    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await acquire_lock("LEFT", gap, 4)
        await robot.set_mode("LEFT", gap, "OFF")
        await robot.release_resource("LEFT", gap)
    # wait its exact active receipt exactly once
    gate_waited = await robot.wait_event("rq2_gate", 4)
    # clear exactly that version after assigned protected scope
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # ---- final homes ----
    await robot.move("LEFT", "left_home", 4)
    await robot.move("RIGHT", "right_home", 4)
