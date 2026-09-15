async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("clamp_pose_lease")
    right_receipt = await robot.observe_authorization("fastener_alignment_lease")
    left_receipt_again = await robot.observe_authorization("clamp_pose_lease")

    if left_receipt.coordination_generation != left_receipt_again.coordination_generation:
        left_receipt = left_receipt_again
        right_receipt = await robot.observe_authorization("fastener_alignment_lease")
    else:
        left_receipt = left_receipt_again

    await robot.protected_action("seat_aligned_fastener", left_receipt, right_receipt)
