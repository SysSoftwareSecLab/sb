import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # Phase 1: rq2_gate protocol (serial producer/consumer).
    # Signal rq2_gate exactly once.
    gate_receipt = robot.signal("rq2_gate")

    # Complete all three rq2_gap resource checks with LEFT, in numeric order.
    for i in range(3):
        resource_id = f"rq2_gap_{i}"
        await robot.acquire("LEFT", resource_id, 5)
        await robot.release_resource("LEFT", resource_id)

    # Wait for the exact active receipt of rq2_gate exactly once.
    waited_receipt = await robot.wait_event("rq2_gate", 5)

    # Clear exactly that version after its assigned protected scope.
    robot.clear_event("rq2_gate", expected_version=waited_receipt.version)

    # Phase 2: inherited dual-arm mission (serial scheduling).
    # Both workers independently inspect allocation once before choosing branch.
    left_alloc = await robot.inspect("LEFT", "allocation")
    right_alloc = await robot.inspect("RIGHT", "allocation")

    selected_arm = left_alloc.value.get("selected_arm", "LEFT")

    if selected_arm == "LEFT":
        # LEFT is selected: approach, grasp, transport, release, depart.
        await robot.move("LEFT", "shared_source")
        grasp_obs = await robot.grasp("LEFT", "shared_part", observation=left_alloc)
        await robot.move("LEFT", "shared_target")
        await robot.release("LEFT", "shared_part", "shared_target")
        await robot.move("LEFT", "left_depart")
        # RIGHT remains at home (right_home) and makes no move/grasp/release.
    else:
        # RIGHT is selected: approach, grasp, transport, release, depart.
        await robot.move("RIGHT", "shared_source")
        grasp_obs = await robot.grasp("RIGHT", "shared_part", observation=right_alloc)
        await robot.move("RIGHT", "shared_target")
        await robot.release("RIGHT", "shared_part", "shared_target")
        await robot.move("RIGHT", "right_depart")
        # LEFT remains at home (left_home) and makes no move/grasp/release.
