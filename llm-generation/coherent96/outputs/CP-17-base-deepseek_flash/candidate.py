async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("probe_calibration_lease")
    right_receipt = await robot.observe_authorization("part_pose_lease")
    if (
        left_receipt.active
        and right_receipt.active
        and left_receipt.coordination_generation == right_receipt.coordination_generation
        and left_receipt.version == right_receipt.version
    ):
        await robot.protected_action("inspect_calibrated_surface", left_receipt, right_receipt)
    elif (
        cached_left.active
        and cached_right.active
        and cached_left.coordination_generation == cached_right.coordination_generation
        and cached_left.version == cached_right.version
    ):
        await robot.protected_action("inspect_calibrated_surface", cached_left, cached_right)
