import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    async def worker_left() -> None:
        await robot.inspect(LEFT, "allocation")
        await robot.move(LEFT, "shared_source")
        await robot.grasp(LEFT, "shared_part")
        await robot.move(LEFT, "shared_target")
        await robot.release(LEFT, "shared_part", "shared_target")
        await robot.move(LEFT, "left_depart")

    async def worker_right() -> None:
        await robot.inspect(RIGHT, "allocation")
        await robot.move(RIGHT, "right_home")

    async def gap_checks() -> None:
        for rid in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
            await robot.acquire(LEFT, rid, 4)
            await robot.release_resource(LEFT, rid)

    async def gate_producer() -> None:
        await gap_checks()
        robot.signal("rq2_gate")

    async def gate_consumer() -> None:
        receipt = await robot.wait_event("rq2_gate", 30)
        await worker_left()
        await worker_right()
        robot.clear_event("rq2_gate", expected_version=receipt.version)

    await asyncio.gather(gate_producer(), gate_consumer())
