async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("housing_support_lease")
    right_receipt = await robot.observe_authorization("cover_alignment_lease")
    if (
        left_receipt.active
        and right_receipt.active
        and left_receipt.coordination_generation == right_receipt.coordination_generation
        and left_receipt.version == right_receipt.version
        and left_receipt.state_id == cached_left.state_id
        and right_receipt.state_id == cached_right.state_id
    ):
        await robot.protected_action("close_aligned_housing", left_receipt, right_receipt)
