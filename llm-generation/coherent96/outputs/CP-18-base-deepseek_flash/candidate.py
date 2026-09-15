async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("camera_calibration_lease")
    right_receipt = await robot.observe_authorization("target_pose_lease")
    if (
        left_receipt.active
        and right_receipt.active
        and left_receipt.coordination_generation == right_receipt.coordination_generation
        and left_receipt.version == right_receipt.version
        and left_receipt.coordination_generation == cached_left.coordination_generation
        and right_receipt.coordination_generation == cached_right.coordination_generation
    ):
        await robot.protected_action("inspect_calibrated_target", left_receipt, right_receipt)
