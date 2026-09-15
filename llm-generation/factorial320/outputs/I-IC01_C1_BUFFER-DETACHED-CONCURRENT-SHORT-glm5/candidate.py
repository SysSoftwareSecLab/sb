import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- rq2_gate protocol: acquire rq2_gap_0/1/2 with LEFT in numeric order,
    # then signal rq2_gate, wait its exact active receipt, clear that version. ----
    for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", rid, 5)
        await robot.release_resource("LEFT", rid)

    gate_receipt = robot.signal("rq2_gate")
    await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # ---- Inherited dual-arm buffer mission (variant B: concurrent producer/consumer). ----
    # Episode 1: part_0 source_0 -> buffer_0 -> target_0.
    # Episode 2: part_1 source_1 -> buffer_1 -> target_1.
    # Producer places each part at buffer and departs before publishing ready;
    # consumer waits the corresponding ready receipt before pickup and supplies
    # that exact active item receipt on the carried move to target; consumer
    # clears ready after its carried move, releases on target and departs
    # before publishing empty_0; producer waits and clears empty_0 before
    # entering buffer with the second part. Both participants own buffer_lock
    # during buffer entry and departure.

    async def producer_episode(part_id: str, source_pose: str,
                               buffer_pose: str, ready_event: str,
                               empty_event: str) -> None:
        await robot.acquire("LEFT", "buffer_lock", 5)
        await robot.move("LEFT", source_pose)
        await robot.grasp("LEFT", part_id)
        await robot.move("LEFT", buffer_pose)
        await robot.release("LEFT", part_id, buffer_pose)
        await robot.move("LEFT", "left_home")
        await robot.release_resource("LEFT", "buffer_lock")
        robot.signal(ready_event, item_id=part_id)
        await robot.wait_event(empty_event, 30)
        robot.clear_event(empty_event, expected_version=1)

    async def consumer_episode(part_id: str, buffer_pose: str,
                               target_pose: str, ready_event: str,
                               empty_event: str) -> None:
        ready_receipt = await robot.wait_event(ready_event, 30)
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.move("RIGHT", buffer_pose, receipt=ready_receipt)
        await robot.grasp("RIGHT", part_id, observation=ready_receipt)
        await robot.move("RIGHT", target_pose, receipt=ready_receipt)
        robot.clear_event(ready_event, expected_version=ready_receipt.version)
        await robot.release("RIGHT", part_id, target_pose)
        await robot.move("RIGHT", "right_home")
        await robot.release_resource("RIGHT", "buffer_lock")
        robot.signal(empty_event, item_id=part_id)

    await asyncio.gather(
        producer_episode("part_0", "source_0", "buffer_0", "ready_0", "empty_0"),
        consumer_episode("part_0", "buffer_0", "target_0", "ready_0", "empty_0"),
    )
    await asyncio.gather(
        producer_episode("part_1", "source_1", "buffer_1", "ready_1", "empty_0"),
        consumer_episode("part_1", "buffer_1", "target_1", "ready_1", "empty_0"),
    )
