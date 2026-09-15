import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- Producer (LEFT) ----
    # Episode 1: part_0
    await robot.acquire("LEFT", "buffer_lock", 120)
    await robot.set_mode("LEFT", "buffer_lock", "OFF")
    await robot.move("LEFT", "source_0")
    await robot.grasp("LEFT", "part_0")
    await robot.move("LEFT", "buffer_0")
    await robot.release("LEFT", "part_0", "buffer_0")
    await robot.move("LEFT", "left_home")
    robot.signal("ready_0", "part_0")

    # Episode 2: part_1
    await robot.acquire("LEFT", "buffer_lock", 120)
    await robot.set_mode("LEFT", "buffer_lock", "OFF")
    await robot.move("LEFT", "left_wait")
    await robot.move("LEFT", "source_1")
    await robot.grasp("LEFT", "part_1")
    await robot.move("LEFT", "left_wait")
    await robot.move("LEFT", "buffer_1")
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_wait")
    await robot.move("LEFT", "left_home")
    robot.signal("ready_1", "part_1")

    # ---- Consumer (RIGHT) ----
    # Episode 1: part_0
    r0 = await robot.wait_event("ready_0", 120)
    await robot.acquire("RIGHT", "buffer_lock", 120)
    await robot.set_mode("RIGHT", "buffer_lock", "OFF")
    await robot.move("RIGHT", "right_home", receipt=r0)
    await robot.grasp("RIGHT", "part_0")
    await robot.move("RIGHT", "right_home")
    robot.clear_event("ready_0", expected_version=r0.version)
    await robot.release_resource("RIGHT", "buffer_lock")
    await robot.move("RIGHT", "target_0")
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_home")
    robot.signal("empty_0", "part_0")

    # Episode 2: part_1
    e0 = await robot.wait_event("empty_0", 120)
    robot.clear_event("empty_0", expected_version=e0.version)

    lc = await robot.inspect("LEFT", "line_clear")
    rr = await robot.refresh("RIGHT", "receiver_ready")

    await robot.acquire("RIGHT", "tool", 120)
    await robot.set_mode("RIGHT", "tool", "OFF")

    r1 = await robot.wait_event("ready_1", 120)
    await robot.acquire("RIGHT", "buffer_lock", 120)
    await robot.set_mode("RIGHT", "buffer_lock", "OFF")
    await robot.move("RIGHT", "right_home", receipt=r1)
    await robot.grasp("RIGHT", "part_1")
    await robot.move("RIGHT", "right_home")
    robot.clear_event("ready_1", expected_version=r1.version)
    await robot.release_resource("RIGHT", "buffer_lock")
    await robot.move("RIGHT", "target_1")
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home")

    await robot.release_resource("RIGHT", "tool")
