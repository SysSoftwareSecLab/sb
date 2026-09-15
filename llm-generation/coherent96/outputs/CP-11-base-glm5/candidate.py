async def consumer_policy(robot, cached_left, cached_right):
    left = await robot.observe_authorization("channel_clearance_lease")
    right = await robot.observe_authorization("cable_pose_lease")
    if (
        left.active
        and right.active
        and left.state_id == "channel_clearance_lease"
        and right.state_id == "cable_pose_lease"
        and left.coordination_generation == right.coordination_generation
        and left.coordination_generation == robot.coordination_generation
    ):
        await robot.protected_action("route_aligned_cable", left, right)
