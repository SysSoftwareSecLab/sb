import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # LONG variant: LEFT acquires tool before source pickup and keeps it across
    # the second-item wait and checks. Release tool on every normal exit.
    tool_acquired = False
    try:
        # Acquire tool before source pickup (LONG).
        await robot.acquire("LEFT", "tool", 5.0)
        tool_acquired = True

        # ---- Episode 1: part_0 ----
        # Producer: LEFT picks part_0 from source_0 and places at buffer_0.
        await robot.move("LEFT", "left_home")
        await robot.grasp("LEFT", "part_0")
        await robot.move("LEFT", "buffer_0")
        await robot.release("LEFT", "part_0", "buffer_0")
        # Immediately depart before ready publication.
        await robot.move("LEFT", "left_wait")

        # Publish ready_0.
        ready0 = robot.signal("ready_0", "part_0")

        # Consumer: RIGHT waits ready_0, picks part_0, carries to target_0.
        r0 = await robot.wait_event("ready_0", 5.0)
        await robot.move("RIGHT", "right_home")
        await robot.grasp("RIGHT", "part_0")
        await robot.move("RIGHT", "target_0", receipt=r0)
        await robot.release("RIGHT", "part_0", "target_0")
        await robot.move("RIGHT", "right_home")

        # Consumer clears ready_0 after carried move, release, and departure.
        robot.clear_event("ready_0", expected_version=r0.version)

        # Publish empty_0.
        empty0 = robot.signal("empty_0")

        # Producer waits and clears empty_0 before entering buffer with part_1.
        e0 = await robot.wait_event("empty_0", 5.0)
        robot.clear_event("empty_0", expected_version=e0.version)

        # ---- Episode 2: part_1 ----
        # Second-item checks: D4 joins them with asyncio.gather inside i==1 branch.
        obs_line, obs_recv = await asyncio.gather(
            robot.inspect("LEFT", "line_clear"),
            robot.inspect("RIGHT", "receiver_ready"),
        )
        # Both public Boolean fields must permit transfer.
        line_val = obs_line.value
        recv_val = obs_recv.value
        if not (isinstance(line_val, dict) and line_val.get("clear") is True):
            raise ContractError("line_clear not clear")
        if not (isinstance(recv_val, dict) and recv_val.get("ready") is True):
            raise ContractError("receiver_ready not ready")

        # Producer: LEFT picks part_1 from source_1 and places at buffer_1.
        await robot.move("LEFT", "left_wait")
        await robot.grasp("LEFT", "part_1")
        await robot.move("LEFT", "buffer_1")
        await robot.release("LEFT", "part_1", "buffer_1")
        # Immediately depart before ready publication.
        await robot.move("LEFT", "left_wait")

        # Publish ready_1.
        ready1 = robot.signal("ready_1", "part_1")

        # Consumer: RIGHT waits ready_1, picks part_1, carries to target_1.
        r1 = await robot.wait_event("ready_1", 5.0)
        await robot.move("RIGHT", "right_home")
        await robot.grasp("RIGHT", "part_1")
        await robot.move("RIGHT", "target_1", receipt=r1)
        await robot.release("RIGHT", "part_1", "target_1")
        await robot.move("RIGHT", "right_home")

        # Consumer clears ready_1 after carried move, release, and departure.
        robot.clear_event("ready_1", expected_version=r1.version)

        # Publish empty_0 again (buffer empty).
        robot.signal("empty_0")

        # Return arms to homes.
        await robot.move("LEFT", "left_home")
        await robot.move("RIGHT", "right_home")

    finally:
        # Release tool on every normal, failure and cancellation exit.
        if tool_acquired:
            try:
                await robot.release_resource("LEFT", "tool")
            except Exception:
                pass
