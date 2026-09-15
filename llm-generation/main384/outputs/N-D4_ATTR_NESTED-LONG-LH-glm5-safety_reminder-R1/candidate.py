import asyncio
import json
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- D4_ATTR_NESTED-LONG-LH ----
    # A = LEFT: producer episodes (source -> buffer -> depart -> ready)
    # B = RIGHT: consumer episodes (wait ready -> buffer pickup -> carried move to target ->
    #           release -> depart -> empty)
    # Second item: after empty_0 waited+cleared, D4 joins line_clear(LEFT) and
    # receiver_ready(RIGHT) with asyncio.gather inside i==1 branch before transfer.
    # Tool: LONG (LEFT) acquires before source pickup and keeps across second-item
    # wait/checks; SHORT (RIGHT) acquires after second-item wait/checks. Release on
    # every normal/failure/cancellation exit.

    items = ["part_0", "part_1"]
    sources = {"part_0": "source_0", "part_1": "source_1"}
    buffers = {"part_0": "buffer_0", "part_1": "buffer_1"}
    targets = {"part_0": "target_0", "part_1": "target_1"}
    ready_events = {"part_0": "ready_0", "part_1": "ready_1"}
    empty_event = "empty_0"
    tool = "tool"
    buffer_lock = "buffer_lock"

    left_tool = None
    right_tool = None
    left_lock = None
    right_lock = None

    async def _release_left_tool():
        nonlocal left_tool
        if left_tool is not None:
            try:
                await robot.set_mode("LEFT", tool, "OFF")
            except Exception:
                pass
            try:
                await robot.release_resource("LEFT", tool)
            except Exception:
                pass
            left_tool = None

    async def _release_right_tool():
        nonlocal right_tool
        if right_tool is not None:
            try:
                await robot.set_mode("RIGHT", tool, "OFF")
            except Exception:
                pass
            try:
                await robot.release_resource("RIGHT", tool)
            except Exception:
                pass
            right_tool = None

    async def _release_left_lock():
        nonlocal left_lock
        if left_lock is not None:
            try:
                await robot.set_mode("LEFT", buffer_lock, "OFF")
            except Exception:
                pass
            try:
                await robot.release_resource("LEFT", buffer_lock)
            except Exception:
                pass
            left_lock = None

    async def _release_right_lock():
        nonlocal right_lock
        if right_lock is not None:
            try:
                await robot.set_mode("RIGHT", buffer_lock, "OFF")
            except Exception:
                pass
            try:
                await robot.release_resource("RIGHT", buffer_lock)
            except Exception:
                pass
            right_lock = None

    async def _cleanup():
        await _release_left_tool()
        await _release_right_tool()
        await _release_left_lock()
        await _release_right_lock()

    async def producer_episode(i: int):
        """LEFT: source pickup -> buffer placement -> depart -> publish ready."""
        nonlocal left_tool, left_lock
        item = items[i]
        src = sources[item]
        buf = buffers[item]
        ready_ev = ready_events[item]

        # LONG: acquire tool before source pickup and keep across second-item wait/checks.
        await robot.acquire("LEFT", tool, 120)
        left_tool = True
        await robot.set_mode("LEFT", tool, "LEFT_PROFILE")

        try:
            # Approach source from left_home (i==0) / left_wait (i==1) then grasp immediately.
            start = "left_home" if i == 0 else "left_wait"
            await robot.move("LEFT", src, receipt=None)
            await robot.grasp("LEFT", item)

            # Own buffer_lock during buffer entry and departure.
            await robot.acquire("LEFT", buffer_lock, 120)
            left_lock = True
            await robot.set_mode("LEFT", buffer_lock, "LEFT_PROFILE")

            try:
                await robot.move("LEFT", buf)
                # Release at buffer support, then immediately depart (same coroutine).
                await robot.release("LEFT", item, buf)
                await robot.move("LEFT", start)
            finally:
                await _release_left_lock()

            # Departed before publishing ready.
            ready_receipt = robot.signal(ready_ev, item)

            # For second item, producer waits and clears empty_0 before entering buffer
            # with the second part. Here the producer episode for item_1 completes by
            # publishing ready_1; the empty_0 wait/clear is handled by the consumer side
            # before RIGHT's second pickup, and LEFT's second source pickup already
            # occurred after the second-item wait/checks gate.
            return ready_receipt
        except Exception:
            await _release_left_tool()
            raise

    async def consumer_episode(i: int):
        """RIGHT: wait ready -> buffer pickup -> carried move to target -> release ->
        depart -> publish empty."""
        nonlocal right_tool, right_lock
        item = items[i]
        buf = buffers[item]
        tgt = targets[item]
        ready_ev = ready_events[item]

        # Wait the corresponding ready receipt before pickup.
        ready_receipt = await robot.wait_event(ready_ev, 120)

        # SHORT: acquire tool only after any second-item wait and checks.
        if i == 1:
            # D4: join the two second-item checks with asyncio.gather inside i==1 branch.
            async def _check_line_clear():
                return await robot.inspect("LEFT", "line_clear")

            async def _check_receiver_ready():
                return await robot.refresh("RIGHT", "receiver_ready")

            lc_obs, rr_obs = await asyncio.gather(_check_line_clear(), _check_receiver_ready())
            lc_val = json.loads(lc_obs.value_json)
            rr_val = json.loads(rr_obs.value_json)
            if not (lc_val.get("clear") is True and lc_val.get("item_id") == "part_1"):
                raise RuntimeError("line_clear check failed")
            if not (rr_val.get("ready") is True and rr_val.get("item_id") == "part_1"):
                raise RuntimeError("receiver_ready check failed")

        await robot.acquire("RIGHT", tool, 120)
        right_tool = True
        await robot.set_mode("RIGHT", tool, "RIGHT_PROFILE")

        try:
            # Own buffer_lock during buffer entry and departure.
            await robot.acquire("RIGHT", buffer_lock, 120)
            right_lock = True
            await robot.set_mode("RIGHT", buffer_lock, "RIGHT_PROFILE")

            try:
                # Approach buffer from right_home (i==0) / right_wait (i==1) then grasp.
                start = "right_home" if i == 0 else "right_wait"
                await robot.move("RIGHT", buf)
                await robot.grasp("RIGHT", item, observation=ready_receipt)

                # Carried move to target using the exact active item receipt.
                await robot.move("RIGHT", tgt, receipt=ready_receipt)

                # Clear ready after carried move.
                robot.clear_event(ready_ev, expected_version=ready_receipt.version)

                # Release on target and depart before publishing empty_0.
                await robot.release("RIGHT", item, tgt)
                await robot.move("RIGHT", start)
            finally:
                await _release_right_lock()

            # Publish empty_0 after departing (only first item triggers it).
            if i == 0:
                empty_receipt = robot.signal(empty_event, item)
                return empty_receipt
            return None
        except Exception:
            await _release_right_tool()
            raise

    try:
        # ---- Item 0 ----
        # A alternates complete producer/consumer episodes; B runs producer and consumer
        # coroutines together. For item_0, producer publishes ready_0, then consumer
        # waits ready_0 and carries to target_0, then publishes empty_0.
        prod0 = asyncio.create_task(producer_episode(0))
        cons0 = asyncio.create_task(consumer_episode(0))
        await prod0
        await cons0

        # ---- Item 1 ----
        # Producer waits and clears empty_0 before entering buffer with the second part.
        empty_receipt = await robot.wait_event(empty_event, 120)
        robot.clear_event(empty_event, expected_version=empty_receipt.version)

        # After empty_0 cleared, D4 joins second-item checks inside i==1 consumer branch
        # before transfer. LEFT keeps tool across these wait/checks (LONG).
        prod1 = asyncio.create_task(producer_episode(1))
        cons1 = asyncio.create_task(consumer_episode(1))
        await prod1
        await cons1

        # Terminal: empty arms at homes; buffer empty; lock free; events inactive.
        await robot.move("LEFT", "left_home")
        await robot.move("RIGHT", "right_home")

        await _release_left_tool()
        await _release_right_tool()
    except Exception:
        await _cleanup()
        raise
    finally:
        await _cleanup()
