async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("conveyor_slot_lease")
    right_receipt = await robot.observe_authorization("package_custody_lease")
    if (
        left_receipt.active
        and right_receipt.active
        and left_receipt.coordination_generation == right_receipt.coordination_generation
        and left_receipt.version == right_receipt.version
    ):
        await robot.protected_action("release_package_to_conveyor", left_receipt, right_receipt)
