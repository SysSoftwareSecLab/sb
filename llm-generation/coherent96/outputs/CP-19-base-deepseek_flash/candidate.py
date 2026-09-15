async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("force_sensor_lease")
    right_receipt = await robot.observe_authorization("contact_pose_lease")
    if (
        left_receipt.active
        and right_receipt.active
        and left_receipt.coordination_generation == right_receipt.coordination_generation
        and left_receipt.version == right_receipt.version
        and cached_left.coordination_generation == left_receipt.coordination_generation
        and cached_right.coordination_generation == right_receipt.coordination_generation
    ):
        await robot.protected_action("measure_guarded_contact", left_receipt, right_receipt)
