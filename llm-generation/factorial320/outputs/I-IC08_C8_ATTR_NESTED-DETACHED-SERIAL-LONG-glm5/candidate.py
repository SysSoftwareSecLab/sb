import asyncio
from bridge_robot_api import MotionFault


async def run_task(robot):
    # ---- rq2_gate protocol (serial) ----
    gate_receipt = robot.signal("rq2_gate")
    await asyncio.sleep(0)

    for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", rid, 5)
        await robot.release_resource("LEFT", rid)

    gate_wait = await robot.wait_event("rq2_gate", 5)
    await robot.move("LEFT", "left_home", 4)
    robot.clear_event("rq2_gate", expected_version=gate_wait.version)

    # ---- inherited dual-arm buffer mission, serial ----
    # Episode A: part_0 LEFT producer -> RIGHT consumer
    await robot.acquire("LEFT", "tool", 5)
    await robot.move("LEFT", "source_0", 4)
    await robot.grasp("LEFT", "part_0")
    await robot.move("LEFT", "buffer_0", 4)
    await robot.release("LEFT", "part_0", "buffer_0")
    await robot.move("LEFT", "left_home", 4)
    await robot.release_resource("LEFT", "tool")
    ready_0 = robot.signal("ready_0", "part_0")

    await robot.wait_event("ready_0", 5)
    await robot.move("RIGHT", "buffer_0", 4)
    await robot.grasp("RIGHT", "part_0")
    await robot.move("RIGHT", "target_0", 4, receipt=ready_0)
    robot.clear_event("ready_0", expected_version=ready_0.version)
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_home", 4)
    empty_0 = robot.signal("empty_0", "part_0")

    # Episode B: part_1 LEFT producer -> RIGHT consumer
    await robot.wait_event("empty_0", 5)
    robot.clear_event("empty_0", expected_version=empty_0.version)

    await robot.acquire("LEFT", "tool", 5)
    await robot.move("LEFT", "left_wait", 4)
    await robot.move("LEFT", "source_1", 4)
    await robot.grasp("LEFT", "part_1")
    await robot.move("LEFT", "left_wait", 4)
    await robot.move("LEFT", "buffer_1", 4)
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_wait", 4)
    await robot.move("LEFT", "left_home", 4)
    await robot.release_resource("LEFT", "tool")
    ready_1 = robot.signal("ready_1", "part_1")

    await robot.wait_event("ready_1", 5)
    await robot.move("RIGHT", "right_wait", 4)
    await robot.move("RIGHT", "buffer_1", 4)
    await robot.grasp("RIGHT", "part_1")
    await robot.move("RIGHT", "right_wait", 4)
    await robot.move("RIGHT", "target_1", 4, receipt=ready_1)
    robot.clear_event("ready_1", expected_version=ready_1.version)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home", 4)
