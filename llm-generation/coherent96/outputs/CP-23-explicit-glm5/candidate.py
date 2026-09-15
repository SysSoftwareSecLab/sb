async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("pallet_support_lease")
    right_receipt = await robot.observe_authorization("case_custody_lease")
    left_receipt = await robot.observe_authorization("pallet_support_lease")
    if left_receipt.coordination_generation != (await robot.observe_authorization("pallet_support_lease")).coordination_generation:
        left_receipt = await robot.observe_authorization("pallet_support_lease")
        right_receipt = await robot.observe_authorization("case_custody_lease")
    await robot.protected_action("release_case_on_pallet", left_receipt, right_receipt)
