from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # SHORT variant: acquire tool only after second-item wait and checks.
    # LEFT = producer, RIGHT = consumer.
    # Two items: part_0 (episode 1), part_1 (episode 2).

    # ---------- Episode 1: part_0 ----------
    # Producer: LEFT picks part_0 at source_0, carries to buffer_0, releases, departs.
    # Consumer: RIGHT waits ready_0, picks part_0 at buffer_0, carries to target_0,
    #           releases, departs, then signals empty_0.

    # Producer episode 1
    await robot.move("LEFT", "source_0")
    obs_p0 = await robot.grasp("LEFT", "part_0")
    await robot.move("LEFT", "buffer_0")
    await robot.release("LEFT", "part_0", "buffer_0")
    await robot.move("LEFT", "left_home")

    # Signal ready_0 for part_0
    ready0 = robot.signal("ready_0", "part_0")

    # Consumer episode 1
    r0 = await robot.wait_event("ready_0", 5.0)
    await robot.move("RIGHT", "buffer_0", receipt=r0)
    obs_r0 = await robot.grasp("RIGHT", "part_0")
    await robot.move("RIGHT", "target_0", receipt=r0)
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_home")

    # Consumer clears ready_0 after carried move complete
    robot.clear_event("ready_0", expected_version=r0.version)

    # Consumer signals empty_0
    empty0 = robot.signal("empty_0", "part_0")

    # ---------- Episode 2: part_1 ----------
    # Producer waits and clears empty_0 before entering buffer with second part.
    e0 = await robot.wait_event("empty_0", 5.0)
    robot.clear_event("empty_0", expected_version=e0.version)

    # SHORT: acquire tool only after second-item wait and checks.
    # Second-item checks: inspect line_clear with LEFT, receiver_ready with RIGHT.
    # D3: serial checks.
    line_obs = await robot.inspect("LEFT", "line_clear")
    recv_obs = await robot.inspect("RIGHT", "receiver_ready")

    # Both public Boolean fields must permit transfer.
    line_val = line_obs.value
    recv_val = recv_obs.value
    if not (isinstance(line_val, dict) and line_val.get("clear") is True):
        raise ContractError("line_clear does not permit transfer")
    if not (isinstance(recv_val, dict) and recv_val.get("ready") is True):
        raise ContractError("receiver_ready does not permit transfer")

    # SHORT: acquire tool after the wait and checks.
    await robot.acquire("LEFT", "tool", 5.0)

    # Producer episode 2: LEFT picks part_1 at source_1, carries to buffer_1, releases, departs.
    await robot.move("LEFT", "source_1")
    obs_p1 = await robot.grasp("LEFT", "part_1")
    await robot.move("LEFT", "buffer_1")
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_home")

    # Release tool on normal exit
    await robot.release_resource("LEFT", "tool")

    # Signal ready_1 for part_1
    ready1 = robot.signal("ready_1", "part_1")

    # Consumer episode 2
    r1 = await robot.wait_event("ready_1", 5.0)
    await robot.move("RIGHT", "buffer_1", receipt=r1)
    obs_r1 = await robot.grasp("RIGHT", "part_1")
    await robot.move("RIGHT", "target_1", receipt=r1)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home")

    # Consumer clears ready_1 after carried move complete
    robot.clear_event("ready_1", expected_version=r1.version)

    # Consumer signals empty_0 again (buffer empty)
    empty0b = robot.signal("empty_0", "part_1")
