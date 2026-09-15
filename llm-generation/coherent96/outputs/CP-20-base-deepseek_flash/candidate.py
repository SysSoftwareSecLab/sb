async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("gauge_calibration_lease")
    right_receipt = await robot.observe_authorization("feature_pose_lease")
    if (
        left_receipt.active
        and right_receipt.active
        and left_receipt.coordination_generation == right_receipt.coordination_generation
        and left_receipt.version == right_receipt.version
    ):
        await robot.protected_action("measure_aligned_feature", left_receipt, right_receipt)
