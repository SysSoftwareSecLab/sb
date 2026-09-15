import asyncio
from bridge_robot_api import Robot


async def _deposit(arm, part, source, pad, wait, depart, robot):
    await robot.move(arm, source)
    await robot.grasp(arm, part)
    await robot.move(arm, pad)
    await robot.release(arm, part, pad)
    await robot.move(arm, wait)
    await robot.move(arm, depart)
    return robot.signal(f"{arm}_ready", part)


async def _consume(arm, peer, peer_pad, wait, target, depart, receipt, robot):
    await robot.move(arm, wait, receipt=receipt)
    await robot.grasp(arm, peer)
    await robot.move(arm, target, receipt=receipt)
    await robot.release(arm, peer, target)
    await robot.move(arm, depart)
    robot.clear_event(f"{arm}_ready", expected_version=receipt.version)


async def _worker(arm, peer, source, pad, wait, target, depart, robot):
    receipt = await _deposit(arm, arm + "_part", source, pad, wait, depart, robot)
    peer_receipt = await robot.wait_event(f"{peer}_ready", 30)
    await _consume(arm, peer + "_part", peer + "_pad", wait, target, depart, peer_receipt, robot)
    robot.clear_event(f"{arm}_ready", expected_version=receipt.version)


async def _gate_producer(robot):
    await robot.move("LEFT", "left_home")
    await robot.move("RIGHT", "right_home")
    return robot.signal("rq2_gate")


async def _gate_consumer(receipt, robot):
    await robot.wait_event("rq2_gate", 30)
    await asyncio.gather(
        _worker("LEFT", "right", "left_source", "left_pad", "left_pickup_wait", "right_target", "left_depart", robot),
        _worker("RIGHT", "left", "right_source", "right_pad", "right_pickup_wait", "left_target", "right_depart", robot),
    )
    robot.clear_event("rq2_gate", expected_version=receipt.version)


async def run_task(robot: Robot):
    receipt = await _gate_producer(robot)
    await _gate_consumer(receipt, robot)
