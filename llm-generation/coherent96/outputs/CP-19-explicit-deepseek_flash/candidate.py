async def consumer_policy(robot, cached_left, cached_right):
    left = await robot.observe_authorization("force_sensor_lease")
    right = await robot.observe_authorization("contact_pose_lease")
    left_again = await robot.observe_authorization("force_sensor_lease")

    if left_again.coordination_generation != left.coordination_generation:
        left = left_again
        right = await robot.observe_authorization("contact_pose_lease")
    else:
        left = left_again

    return await robot.protected_action("measure_guarded_contact", left, right)
