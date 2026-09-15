from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # Variant A: SERIAL structure.
    # A alternates complete producer/consumer episodes.
    # Producer: LEFT places part_0 at buffer_0, departs, signals ready_0.
    # Consumer: RIGHT waits ready_0, picks part_0 from buffer_0, carries to target_0,
    #           clears ready_0 after carried move, releases on target_0, departs,
    #           signals empty_0.
    # Then part_1: LEFT waits empty_0, clears it, approaches source_1 from left_wait,
    #              grasps part_1, moves to buffer_1, releases, departs, signals ready_1.
    # RIGHT waits ready_1, picks part_1 from buffer_1, carries to target_1,
    #       clears ready_1 after carried move, releases on target_1, departs,
    #       signals empty_0 (final).

    # ---- Episode 0: part_0 ----

    # Producer LEFT: approach source_0 from left_home, grasp part_0
    await robot.move("LEFT", "source_0")
    obs_p0 = await robot.grasp("LEFT", "part_0")

    # Acquire buffer_lock before buffer entry
    await robot.acquire("LEFT", "buffer_lock", 5)

    # Move to buffer_0 (same coords as buffer_1)
    await robot.move("LEFT", "buffer_0")

    # Release part_0 at buffer_0
    await robot.release("LEFT", "part_0", "buffer_0")

    # Immediate separating departure
    await robot.move("LEFT", "left_wait")

    # Release buffer_lock after departure
    await robot.release_resource("LEFT", "buffer_lock")

    # Signal ready_0
    ready0 = robot.signal("ready_0")

    # Consumer RIGHT: wait ready_0
    ready0_recv = await robot.wait_event("ready_0", 10)

    # Acquire buffer_lock before buffer entry
    await robot.acquire("RIGHT", "buffer_lock", 5)

    # Approach buffer_0 from right_home, grasp part_0
    await robot.move("RIGHT", "buffer_0")
    obs_p0_r = await robot.grasp("RIGHT", "part_0")

    # Depart buffer with part_0
    await robot.move("RIGHT", "right_wait")

    # Release buffer_lock after departure
    await robot.release_resource("RIGHT", "buffer_lock")

    # Carried move to target_0 with the exact active ready_0 receipt
    await robot.move("RIGHT", "target_0", receipt=ready0_recv)

    # Clear ready_0 after carried move completes
    robot.clear_event("ready_0", expected_version=ready0_recv.version)

    # Release part_0 on target_0
    await robot.release("RIGHT", "part_0", "target_0")

    # Immediate separating departure
    await robot.move("RIGHT", "right_home")

    # Signal empty_0
    empty0 = robot.signal("empty_0")

    # ---- Episode 1: part_1 ----

    # Producer LEFT: wait empty_0, clear it
    empty0_recv = await robot.wait_event("empty_0", 10)
    robot.clear_event("empty_0", expected_version=empty0_recv.version)

    # Approach source_1 from left_wait, grasp part_1
    await robot.move("LEFT", "source_1")
    obs_p1 = await robot.grasp("LEFT", "part_1")

    # Acquire buffer_lock before buffer entry
    await robot.acquire("LEFT", "buffer_lock", 5)

    # Move to buffer_1 (same coords as buffer_0)
    await robot.move("LEFT", "buffer_1")

    # Release part_1 at buffer_1
    await robot.release("LEFT", "part_1", "buffer_1")

    # Immediate separating departure
    await robot.move("LEFT", "left_home")

    # Release buffer_lock after departure
    await robot.release_resource("LEFT", "buffer_lock")

    # Signal ready_1
    ready1 = robot.signal("ready_1")

    # Consumer RIGHT: wait ready_1
    ready1_recv = await robot.wait_event("ready_1", 10)

    # Acquire buffer_lock before buffer entry
    await robot.acquire("RIGHT", "buffer_lock", 5)

    # Approach buffer_1 from right_wait, grasp part_1
    await robot.move("RIGHT", "buffer_1")
    obs_p1_r = await robot.grasp("RIGHT", "part_1")

    # Depart buffer with part_1
    await robot.move("RIGHT", "right_wait")

    # Release buffer_lock after departure
    await robot.release_resource("RIGHT", "buffer_lock")

    # Carried move to target_1 with the exact active ready_1 receipt
    await robot.move("RIGHT", "target_1", receipt=ready1_recv)

    # Clear ready_1 after carried move completes
    robot.clear_event("ready_1", expected_version=ready1_recv.version)

    # Release part_1 on target_1
    await robot.release("RIGHT", "part_1", "target_1")

    # Immediate separating departure
    await robot.move("RIGHT", "right_home")

    # Signal empty_0 (final, buffer empty)
    robot.signal("empty_0")
