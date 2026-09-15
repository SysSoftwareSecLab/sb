import asyncio

from bridge_robot_api import Robot


async def _producer_episode(robot: Robot, part_id: str, source_pose: str,
                             buffer_pose: str, ready_event: str,
                             empty_event: str, left_wait_pose: str) -> None:
    # Approach source and grasp part.
    await robot.move("LEFT", source_pose)
    await robot.grasp("LEFT", part_id)

    # Acquire buffer lock, enter buffer, release part, depart, release lock.
    await robot.acquire("LEFT", "buffer_lock", 5)
    await robot.move("LEFT", buffer_pose)
    await robot.release("LEFT", part_id, buffer_pose)
    await robot.move("LEFT", left_wait_pose)
    await robot.release_resource("LEFT", "buffer_lock")

    # Publish ready receipt for this part.
    ready_receipt = robot.signal(ready_event, part_id)

    # Wait for consumer to clear ready, then wait for empty_0 signal.
    await robot.wait_event(ready_event, 30)
    robot.clear_event(ready_event, expected_version=ready_receipt.version)
    await robot.wait_event(empty_event, 30)


async def _consumer_episode(robot: Robot, part_id: str, buffer_pose: str,
                            target_pose: str, right_wait_pose: str,
                            ready_event: str, empty_event: str) -> None:
    # Wait for producer's ready receipt for this part.
    ready_receipt = await robot.wait_event(ready_event, 30)

    # Acquire buffer lock, approach buffer, grasp part, depart, release lock.
    await robot.acquire("RIGHT", "buffer_lock", 5)
    await robot.move("RIGHT", buffer_pose)
    await robot.grasp("RIGHT", part_id, observation=ready_receipt)
    await robot.move("RIGHT", right_wait_pose)
    await robot.release_resource("RIGHT", "buffer_lock")

    # Carried move to target using the exact active ready receipt.
    await robot.move("RIGHT", target_pose, receipt=ready_receipt)

    # Release on target, depart, release lock, clear ready, publish empty_0.
    await robot.release("RIGHT", part_id, target_pose)
    await robot.move("RIGHT", "right_home")
    robot.clear_event(ready_event, expected_version=ready_receipt.version)
    robot.signal(empty_event, part_id)


async def run_task(robot: Robot) -> None:
    # FOR -> PAR_JOIN -> consumer IF structural-OOD shape.
    episodes = [
        ("part_0", "source_0", "buffer_0", "ready_0", "target_0"),
        ("part_1", "source_1", "buffer_1", "ready_1", "target_1"),
    ]

    for part_id, source_pose, buffer_pose, ready_event, target_pose in episodes:
        producer = asyncio.create_task(
            _producer_episode(
                robot, part_id, source_pose, buffer_pose, ready_event,
                "empty_0", "left_wait",
            )
        )
        consumer = asyncio.create_task(
            _consumer_episode(
                robot, part_id, buffer_pose, target_pose, "right_wait",
                ready_event, "empty_0",
            )
        )
        await asyncio.gather(producer, consumer)

    # rq2_gate inactive at return: signal then clear to leave it inactive.
    gate_receipt = robot.signal("rq2_gate")
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
