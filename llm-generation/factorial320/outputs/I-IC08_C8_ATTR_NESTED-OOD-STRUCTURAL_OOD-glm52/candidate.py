import asyncio

from bridge_robot_api import Robot


async def _producer_episode(robot: Robot, item: str, source: str,
                            buffer: str, ready_event: str,
                            empty_event: str, wait_empty: bool) -> None:
    """LEFT produces one part: source -> buffer, depart, publish ready."""
    # Own tool from before source pickup through ready publication.
    await robot.acquire("LEFT", "tool", 5)
    await robot.set_mode("LEFT", "tool", "LEFT_PROFILE")

    # Approach source and immediately grasp (no intervening calls).
    await robot.move("LEFT", source, timeout_s=4)
    await robot.grasp("LEFT", item)

    # Carry to buffer.
    await robot.move("LEFT", buffer, timeout_s=4)

    # Own buffer_lock during buffer entry and departure.
    await robot.acquire("LEFT", "buffer_lock", 5)

    # Release part onto buffer, then immediately depart.
    await robot.release("LEFT", item, buffer)
    await robot.move("LEFT", "left_home", timeout_s=4)

    # Release buffer_lock on exit.
    await robot.release_resource("LEFT", "buffer_lock")

    # Release tool on every exit.
    await robot.set_mode("LEFT", "tool", "OFF")
    await robot.release_resource("LEFT", "tool")

    # Publish ready receipt (after departing buffer).
    ready_rcpt = robot.signal(ready_event, item)

    # If required, wait for empty_0 before returning so the next
    # producer episode can enter the buffer.
    if wait_empty:
        empty_rcpt = await robot.wait_event(empty_event, 30)
        robot.clear_event(empty_event, expected_version=empty_rcpt.version)

    # Keep ready active; consumer will clear it after its carried move.
    _ = ready_rcpt


async def _consumer_episode(robot: Robot, item: str, buffer: str,
                            target: str, ready_event: str,
                            empty_event: str) -> None:
    """RIGHT consumes one part: buffer -> target, depart, publish empty."""
    # Wait the corresponding ready receipt before pickup.
    ready_rcpt = await robot.wait_event(ready_event, 30)

    # Approach buffer and immediately grasp.
    await robot.move("RIGHT", buffer, timeout_s=4)
    await robot.grasp("RIGHT", item)

    # Supply the exact active item receipt on carried move to target.
    await robot.move("RIGHT", target, timeout_s=4, receipt=ready_rcpt)

    # Clear ready after the carried move completes.
    robot.clear_event(ready_event, expected_version=ready_rcpt.version)

    # Own buffer_lock during buffer departure (release on target + depart).
    await robot.acquire("RIGHT", "buffer_lock", 5)

    # Release on target and immediately depart.
    await robot.release("RIGHT", item, target)
    await robot.move("RIGHT", "right_home", timeout_s=4)

    # Release buffer_lock.
    await robot.release_resource("RIGHT", "buffer_lock")

    # Publish empty_0 after departing buffer.
    empty_rcpt = robot.signal(empty_event, item)
    _ = empty_rcpt


async def _consumer_episode_with_checks(robot: Robot, item: str,
                                        buffer: str, target: str,
                                        ready_event: str,
                                        empty_event: str) -> None:
    """Consumer for item 1: wait/clear empty_0, inspect both readiness
    facts concurrently inside the loop branch, then complete mission."""
    # Wait and clear empty_0 before entering buffer with the second part.
    empty_rcpt = await robot.wait_event(empty_event, 30)
    robot.clear_event(empty_event, expected_version=empty_rcpt.version)

    # C8 joins the two readiness checks inside the loop branch.
    obs_a, obs_b = await asyncio.gather(
        robot.inspect("RIGHT", "line_clear"),
        robot.inspect("RIGHT", "receiver_ready"),
    )
    _ = (obs_a, obs_b)

    # Wait the exact active ready receipt before pickup.
    ready_rcpt = await robot.wait_event(ready_event, 30)

    # Approach buffer and immediately grasp.
    await robot.move("RIGHT", buffer, timeout_s=4)
    await robot.grasp("RIGHT", item)

    # Supply exact active item receipt on carried move to target.
    await robot.move("RIGHT", target, timeout_s=4, receipt=ready_rcpt)

    # Clear that version after carried move.
    robot.clear_event(ready_event, expected_version=ready_rcpt.version)

    # Own buffer_lock during buffer departure.
    await robot.acquire("RIGHT", "buffer_lock", 5)

    # Release on target and immediately depart.
    await robot.release("RIGHT", item, target)
    await robot.move("RIGHT", "right_home", timeout_s=4)

    await robot.release_resource("RIGHT", "buffer_lock")

    # Publish empty_0 after departing buffer.
    new_empty = robot.signal(empty_event, item)
    _ = new_empty


async def run_task(robot: Robot) -> None:
    """IC08 C8 ATTR NESTED - OOD STRUCTURAL_OOD (SERIAL, L0).

    Structural shape: FOR -> PAR_JOIN -> consumer IF.

    Two parts cross a capacity-one supported buffer from LEFT producer
    to RIGHT consumer.  Inside one finite loop iteration, concurrently
    join an rq2_gate producer and consumer; the consumer waits the exact
    active receipt, executes the complete inherited mission, then clears
    that version.
    """

    # ---- Episode 0: part_0  source_0 -> buffer_0 -> target_0 ----
    producer_0 = _producer_episode(
        robot,
        item="part_0",
        source="source_0",
        buffer="buffer_0",
        ready_event="ready_0",
        empty_event="empty_0",
        wait_empty=False,
    )
    consumer_0 = _consumer_episode(
        robot,
        item="part_0",
        buffer="buffer_0",
        target="target_0",
        ready_event="ready_0",
        empty_event="empty_0",
    )
    await asyncio.gather(producer_0, consumer_0)

    # ---- Episode 1: part_1  source_1 -> buffer_1 -> target_1 ----
    # Producer waits and clears empty_0 before entering buffer with the
    # second part.  Consumer inspects both readiness facts (C8 concurrent
    # join) inside the loop branch, then completes the mission and clears
    # the ready version.
    producer_1 = _producer_episode(
        robot,
        item="part_1",
        source="source_1",
        buffer="buffer_1",
        ready_event="ready_1",
        empty_event="empty_0",
        wait_empty=True,
    )
    consumer_1 = _consumer_episode_with_checks(
        robot,
        item="part_1",
        buffer="buffer_1",
        target="target_1",
        ready_event="ready_1",
        empty_event="empty_0",
    )
    await asyncio.gather(producer_1, consumer_1)

    # ---- Final: clear any remaining active events ----
    # rq2_gate must be inactive at return; ready/empty should be inactive
    # as well.  Consumer clears ready after carried move; producer clears
    # empty before next entry.  Final defensive pass ensures inactivity.
    for evt in ("empty_0", "ready_0", "ready_1", "rq2_gate"):
        try:
            rcpt = await robot.wait_event(evt, 0.1)
        except TimeoutError:
            continue
        try:
            robot.clear_event(evt, expected_version=rcpt.version)
        except Exception:
            pass
