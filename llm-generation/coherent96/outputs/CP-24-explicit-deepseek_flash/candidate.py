async def consumer_policy(robot, cached_left, cached_right):
    left1 = await robot.observe_authorization("conveyor_slot_lease")
    right1 = await robot.observe_authorization("package_custody_lease")
    left2 = await robot.observe_authorization("conveyor_slot_lease")

    if left1.coordination_generation != left2.coordination_generation:
        right2 = await robot.observe_authorization("package_custody_lease")
        left_receipt = left2
        right_receipt = right2
    else:
        left_receipt = left2
        right_receipt = right1

    await robot.protected_action("release_package_to_conveyor", left_receipt, right_receipt)
