import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Shared mutable state for the two concurrent workers.
    state = {
        "left_ready_receipt": None,
        "right_ready_receipt": None,
        "rq2_gate_receipt": None,
    }

    async def left_worker() -> None:
        # Deposit LEFT's own part (left_part) on left_pad.
        await robot.move("LEFT", "left_pad")
        await robot.release("LEFT", "left_part", "left_pad")
        await robot.move("LEFT", "left_clear")
        state["left_ready_receipt"] = robot.signal("left_ready", "left_part")

        # Wait for peer (RIGHT) ready before consuming peer item.
        right_receipt = await robot.wait_event("right_ready", 30)
        state["right_ready_receipt"] = right_receipt

        # Move to pickup wait pose, then approach and grasp peer item.
        await robot.move("LEFT", "left_pickup_wait")
        await robot.move("LEFT", "right_pad")
        await robot.grasp("LEFT", "right_part")

        # Carry peer item to LEFT's target using the active peer-item receipt.
        await robot.move("LEFT", "left_target", receipt=right_receipt)
        await robot.release("LEFT", "right_part", "left_target")
        await robot.move("LEFT", "left_depart")

        # Clear the consumed peer ready event after the carrying move completed.
        robot.clear_event("right_ready", expected_version=right_receipt.version)

    async def right_worker() -> None:
        # Deposit RIGHT's own part (right_part) on right_pad.
        await robot.move("RIGHT", "right_pad")
        await robot.release("RIGHT", "right_part", "right_pad")
        await robot.move("RIGHT", "right_clear")
        state["right_ready_receipt"] = robot.signal("right_ready", "right_part")

        # Wait for peer (LEFT) ready before consuming peer item.
        left_receipt = await robot.wait_event("left_ready", 30)
        state["left_ready_receipt"] = left_receipt

        # Move to pickup wait pose, then approach and grasp peer item.
        await robot.move("RIGHT", "right_pickup_wait")
        await robot.move("RIGHT", "left_pad")
        await robot.grasp("RIGHT", "left_part")

        # Carry peer item to RIGHT's target using the active peer-item receipt.
        await robot.move("RIGHT", "right_target", receipt=left_receipt)
        await robot.release("RIGHT", "left_part", "right_target")
        await robot.move("RIGHT", "right_depart")

        # Clear the consumed peer ready event after the carrying move completed.
        robot.clear_event("left_ready", expected_version=left_receipt.version)

    async def inherited_mission() -> None:
        await asyncio.gather(left_worker(), right_worker())

    async def rq2_gate_scope() -> None:
        # Signal rq2_gate exactly once.
        gate_receipt = robot.signal("rq2_gate")
        state["rq2_gate_receipt"] = gate_receipt

        # Complete all three rq2_gap resource checks, in numeric order, once each.
        for resource_id in ("rq2_gap_0", "rq2_gap_1", "rq2_gap_2"):
            await robot.acquire("LEFT", resource_id, 30)
            await robot.release_resource("LEFT", resource_id)

        # Only after the resource checks, wait for the exact active rq2_gate receipt.
        waited_receipt = await robot.wait_event("rq2_gate", 30)

        # Keep rq2_gate active while executing the complete inherited dual-arm mission.
        await inherited_mission()

        # Clear rq2_gate only after the mission, using the exact waited version.
        robot.clear_event("rq2_gate", expected_version=waited_receipt.version)

    await rq2_gate_scope()
