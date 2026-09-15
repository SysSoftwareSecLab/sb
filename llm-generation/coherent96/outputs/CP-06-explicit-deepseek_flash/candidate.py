async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("human_zone_clearance")
    right_receipt = await robot.observe_authorization("part_custody_lease")
    left_again = await robot.observe_authorization("human_zone_clearance")

    if left_again.coordination_generation != left_receipt.coordination_generation:
        left_receipt = left_again
        right_receipt = await robot.observe_authorization("part_custody_lease")
    else:
        left_receipt = left_again

    await robot.protected_action("complete_guarded_handover", left_receipt, right_receipt)
