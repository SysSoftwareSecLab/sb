async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("bore_clearance_lease")
    right_receipt = await robot.observe_authorization("pin_alignment_lease")
    left_receipt_again = await robot.observe_authorization("bore_clearance_lease")

    if left_receipt.coordination_generation != left_receipt_again.coordination_generation:
        left_receipt = left_receipt_again
        right_receipt = await robot.observe_authorization("pin_alignment_lease")
    else:
        left_receipt = left_receipt_again

    await robot.protected_action("insert_aligned_pin", left_receipt, right_receipt)
