import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Helper to inspect allocation fact
    async def inspect_allocation(arm: str) -> Observation:
        return await robot.inspect(arm, "allocation")

    # Phase 1: Concurrent Inspections
    # Both workers inspect allocation independently before choosing branch.
    obs_left, obs_right = await asyncio.gather(
        inspect_allocation("LEFT"),
        inspect_allocation("RIGHT")
    )

    # Determine selected arm from the observation
    # The observation value is a dict: {"item_id": "shared_part", "selected_arm": "LEFT"}
    selected_arm = obs_left.value["selected_arm"]
    unselected_arm = "RIGHT" if selected_arm == "LEFT" else "LEFT"

    # Phase 2: Resource Checks (LEFT arm only)
    # Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order.
    # Must complete these before signalling rq2_gate.
    async def check_resource(resource_id: str):
        await robot.acquire("LEFT", resource_id, timeout_s=4.0)
        await robot.release_resource("LEFT", resource_id)

    await check_resource("rq2_gap_0")
    await check_resource("rq2_gap_1")
    await check_resource("rq2_gap_2")

    # Phase 3: Gate Protocol
    # Signal rq2_gate exactly once, wait its exact active receipt exactly once,
    # and clear exactly that version after its assigned protected scope.
    # The protected scope is the inherited dual-arm mission.
    gate_receipt = robot.signal("rq2_gate")
    gate_wait_receipt = await robot.wait_event("rq2_gate", timeout_s=4.0)

    # Phase 4: Inherited Dual-Arm Mission (Concurrent)
    # Selected arm: Approach -> Grasp (with obs) -> Move (Target) -> Release -> Depart
    # Unselected arm: Move (Depart) -> Wait (for selected arm to finish) -> Home (optional, but goal says nonselected at right_home/left_home)
    # Note: Goal says "nonselected RIGHT empty at right_home". If LEFT is selected, RIGHT must end at right_home.
    # Initial poses: LEFT at left_home, RIGHT at right_home.
    # Depart poses: left_depart, right_depart.
    # If LEFT is selected: LEFT moves to target then depart. RIGHT moves to depart then home.
    # If RIGHT is selected: RIGHT moves to target then depart. LEFT moves to depart then home.

    async def selected_mission(arm: str, obs: Observation):
        start_pose = "left_home" if arm == "LEFT" else "right_home"
        depart_pose = "left_depart" if arm == "LEFT" else "right_depart"
        
        # Approach
        await robot.move(arm, start_pose)
        # Grasp (must carry current allocation observation)
        await robot.grasp(arm, "shared_part", observation=obs)
        # Transport
        await robot.move(arm, "shared_target")
        # Release
        await robot.release(arm, "shared_part", "shared_target")
        # Depart
        await robot.move(arm, depart_pose)

    async def unselected_mission(arm: str):
        home_pose = "left_home" if arm == "LEFT" else "right_home"
        depart_pose = "left_depart" if arm == "LEFT" else "right_depart"
        
        # Move to depart
        await robot.move(arm, depart_pose)
        # Wait for selected arm to finish (implicit via gather)
        # Return to home as per goal state
        await robot.move(arm, home_pose)

    # Use the observation from the selected arm for the grasp
    selected_obs = obs_left if selected_arm == "LEFT" else obs_right

    await asyncio.gather(
        selected_mission(selected_arm, selected_obs),
        unselected_mission(unselected_arm)
    )

    # Phase 5: Clear Gate
    # Clear exactly the version waited on.
    robot.clear_event("rq2_gate", expected_version=gate_wait_receipt.version)
