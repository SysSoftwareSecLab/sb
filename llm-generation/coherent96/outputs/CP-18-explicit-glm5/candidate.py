async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("camera_calibration_lease")
    right_receipt = await robot.observe_authorization("target_pose_lease")
    left_receipt_again = await robot.observe_authorization("camera_calibration_lease")
    if left_receipt.coordination_generation != left_receipt_again.coordination_generation:
        left_receipt = left_receipt_again
        right_receipt = await robot.observe_authorization("target_pose_lease")
    await robot.protected_action("inspect_calibrated_target", left_receipt, right_receipt)
