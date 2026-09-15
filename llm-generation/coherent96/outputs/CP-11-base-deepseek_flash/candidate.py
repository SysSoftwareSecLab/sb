async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("channel_clearance_lease")
    right_receipt = await robot.observe_authorization("cable_pose_lease")
    if (
        left_receipt.active
        and right_receipt.active
        and left_receipt.coordination_generation == right_receipt.coordination_generation
        and left_receipt.version == right_receipt.version
    ):
        await robot.protected_action("route_aligned_cable", left_receipt, right_receipt)
