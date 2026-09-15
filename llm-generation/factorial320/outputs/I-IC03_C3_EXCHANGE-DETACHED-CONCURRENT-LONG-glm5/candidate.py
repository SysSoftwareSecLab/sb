import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- Phase 1: rq2_gate protocol (signal -> gap checks -> wait -> clear) ----
    gate_receipt = robot.signal("rq2_gate")

    for gap in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
        await robot.acquire("LEFT", gap, 5)
        await robot.release_resource("LEFT", gap)

    gate_waited = await robot.wait_event("rq2_gate", 5)
    robot.clear_event("rq2_gate", expected_version=gate_waited.version)

    # ---- Phase 2: inherited dual-arm exchange (variant B: two concurrent workers) ----
    left_ready_initial = 0
    right_ready_initial = 0

    async def left_worker() -> None:
        # Deposit LEFT's own part (left_part) on right_pad.
        await robot.move("LEFT", "left_source")
        left_grasp_obs = await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "right_pad")
        await robot.release("LEFT", "left_part", "right_pad")
        await robot.move("LEFT", "right_clear")
        left_ready_receipt = robot.signal("left_ready", "left_part")

        # Wait for peer ready before consuming peer item.
        right_ready_receipt = await robot.wait_event("right_ready", 30)

        # Carry move to LEFT's own target (left_target) with the exact active peer receipt.
        await robot.move(
            "LEFT", "left_pickup_wait", receipt=right_ready_receipt
        )
        await robot.grasp("RIGHT", "right_part", observation=left_grasp_obs)
        await robot.move("LEFT", "left_target", receipt=right_ready_receipt)
        robot.clear_event("right_ready", expected_version=right_ready_receipt.version)

        # Depart empty.
        await robot.move("LEFT", "left_depart")
        robot.clear_event("left_ready", expected_version=left_ready_receipt.version)

    async def right_worker() -> None:
        # Deposit RIGHT's own part (right_part) on left_pad.
        await robot.move("RIGHT", "right_source")
        right_grasp_obs = await robot.grasp("RIGHT", "right_part")
        await robot.move("RIGHT", "left_pad")
        await robot.release("RIGHT", "right_part", "left_pad")
        await robot.move("RIGHT", "left_clear")
        right_ready_receipt = robot.signal("right_ready", "right_part")

        # Wait for peer ready before consuming peer item.
        left_ready_receipt = await robot.wait_event("left_ready", 30)

        # Carry move to RIGHT's own target (right_target) with the exact active peer receipt.
        await robot.move(
            "RIGHT", "right_pickup_wait", receipt=left_ready_receipt
        )
        await robot.grasp("LEFT", "left_part", observation=right_grasp_obs)
        await robot.move("RIGHT", "right_target", receipt=left_ready_receipt)
        robot.clear_event("left_ready", expected_version=left_ready_receipt.version)

        # Depart empty.
        await robot.move("RIGHT", "right_depart")
        robot.clear_event("right_ready", expected_version=right_ready_receipt.version)

    await asyncio.gather(left_worker(), right_worker())
