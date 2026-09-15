async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = cached_left
    right_receipt = cached_right
    left_receipt = await robot.observe_authorization("support_grip_lease")
    right_receipt = await robot.observe_authorization("carrier_custody_lease")
    left_receipt = await robot.observe_authorization("support_grip_lease")
    if left_receipt.coordination_generation != cached_left.coordination_generation:
        right_receipt = await robot.observe_authorization("carrier_custody_lease")
    await robot.protected_action("transfer_supported_carrier", left_receipt, right_receipt)
