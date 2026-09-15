async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("pallet_support_lease")
    right_receipt = await robot.observe_authorization("case_custody_lease")
    if (
        left_receipt.active
        and right_receipt.active
        and left_receipt.state_id == "pallet_support_lease"
        and right_receipt.state_id == "case_custody_lease"
        and left_receipt.coordination_generation == right_receipt.coordination_generation
        and left_receipt.version == right_receipt.version
    ):
        await robot.protected_action("release_case_on_pallet", left_receipt, right_receipt)
