async def consumer_policy(robot, cached_left, cached_right):
    left = await robot.observe_authorization("housing_support_lease")
    right = await robot.observe_authorization("cover_alignment_lease")
    left_again = await robot.observe_authorization("housing_support_lease")

    if left.coordination_generation != left_again.coordination_generation:
        left = left_again
        right = await robot.observe_authorization("cover_alignment_lease")
    else:
        left = left_again

    await robot.protected_action("close_aligned_housing", left, right)
