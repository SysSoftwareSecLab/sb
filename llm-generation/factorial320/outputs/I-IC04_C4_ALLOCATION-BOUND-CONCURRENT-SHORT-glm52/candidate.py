import asyncio

from bridge_robot_api import Robot


async def _inspect_allocation(robot: Robot, arm: str):
    return await robot.inspect(arm, "allocation")


async def _left_worker(robot: Robot, alloc_obs):
    # Required order: inspect allocation once before choosing branch.
    await _inspect_allocation(robot, "LEFT")

    # Selected arm (LEFT) performs the transport.
    await robot.move("LEFT", "shared_source", receipt=None)
    grasp_obs = await robot.grasp("LEFT", "shared_part", observation=alloc_obs)
    await robot.move("LEFT", "shared_target", receipt=None)
    await robot.release("LEFT", "shared_part", "shared_target")
    # Immediate separating departure after release.
    await robot.move("LEFT", "left_depart", receipt=None)

    # rq2_gap resource checks in numeric order, once each, never retained.
    for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", rid, 5)
        await robot.release_resource("LEFT", rid)


async def _right_worker(robot: Robot):
    # Required order: inspect allocation once before choosing branch.
    await _inspect_allocation(robot, "RIGHT")

    # Unselected arm (RIGHT) makes no move/grasp/release call; remains at home.
    return


async def _gate_producer(robot: Robot):
    # Complete all three rq2_gap resource checks before signalling rq2_gate.
    # (Checks are performed by the LEFT worker above; this coroutine signals
    #  after the LEFT worker has finished them.)
    receipt = robot.signal("rq2_gate")
    return receipt


async def _gate_consumer(robot: Robot, expected_version: int):
    # Wait the exact active receipt exactly once.
    await robot.wait_event("rq2_gate", 5)
    # Clear exactly that version after the assigned protected scope.
    robot.clear_event("rq2_gate", expected_version=expected_version)


async def run_task(robot: Robot) -> None:
    # Both workers independently inspect allocation once before choosing branch.
    left_alloc = await _inspect_allocation(robot, "LEFT")
    await _inspect_allocation(robot, "RIGHT")

    # Concurrent scheduling for inherited dual-arm mission and gate lifecycle.
    async def mission():
        await asyncio.gather(
            _left_worker(robot, left_alloc),
            _right_worker(robot),
        )

    async def gate():
        receipt = await _gate_producer(robot)
        await _gate_consumer(robot, receipt.version)

    await asyncio.gather(mission(), gate())
