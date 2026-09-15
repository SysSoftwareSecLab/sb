import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Task: Move left_part to left_target, right_part to right_target.
    # Depart: LEFT to left_depart, RIGHT to right_depart.
    # Constraint: D5_FRESHNESS-SHORT-L0.
    # Development obligation: "Version-selected observation after another arm releases an invalidator".
    # Interpretation: The 'route' observation (fact_id='route') must be obtained (via inspect)
    # *after* the other arm (RIGHT) performs a release that invalidates it.
    # Since 'route' is associated with 'left_part', and 'h_variant.invalidates' is true,
    # releasing 'right_part' (the peer) should invalidate 'route'.
    # Therefore, RIGHT must release right_part BEFORE LEFT inspects 'route'.
    # LEFT must then use this fresh observation to grasp left_part (implied by "Version-selected").
    # Finally, LEFT releases left_part and departs.

    # 1. RIGHT Arm Sequence (Peer/Invalidator)
    # Move to source, grasp part, move to target, release part.
    # This release triggers invalidation of 'route'.
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")

    # 2. LEFT Arm Sequence (Dependent)
    # Wait for invalidation event (peer release) implicitly by ordering.
    # Inspect 'route' to get the fresh version (Version-selected).
    route_obs: Observation = await robot.inspect("LEFT", "route")
    
    # Move to source, grasp part using the fresh observation.
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part", observation=route_obs)
    
    # Move to target, release part.
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    
    # 3. Departure
    # Both arms move to departure poses.
    # RIGHT can depart immediately after its release.
    # LEFT departs after its release.
    # These can happen concurrently.
    await asyncio.gather(
        robot.move("RIGHT", "right_depart"),
        robot.move("LEFT", "left_depart")
    )
