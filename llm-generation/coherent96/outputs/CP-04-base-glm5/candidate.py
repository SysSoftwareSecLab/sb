async def consumer_policy(robot, cached_left, cached_right):
    fresh_left = await robot.observe_authorization("housing_support_lease")
    fresh_right = await robot.observe_authorization("cover_alignment_lease")
    if (
        cached_left.state_id == "housing_support_lease"
        and cached_right.state_id == "cover_alignment_lease"
        and fresh_left.state_id == "housing_support_lease"
        and fresh_right.state_id == "cover_alignment_lease"
        and cached_left.active
        and cached_right.active
        and fresh_left.active
        and fresh_right.active
        and cached_left.coordination_generation == cached_right.coordination_generation
        and fresh_left.coordination_generation == fresh_right.coordination_generation
        and cached_left.coordination_generation == fresh_left.coordination_generation
        and cached_left.version == cached_right.version
        and fresh_left.version == fresh_right.version
        and cached_left.version == fresh_left.version
    ):
        await robot.protected_action("close_aligned_housing", cached_left, cached_right)
