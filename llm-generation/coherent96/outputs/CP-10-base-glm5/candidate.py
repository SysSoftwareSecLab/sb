async def consumer_policy(robot, cached_left, cached_right):
    fresh_left = await robot.observe_authorization("bore_clearance_lease")
    fresh_right = await robot.observe_authorization("pin_alignment_lease")
    if (
        cached_left.state_id == "bore_clearance_lease"
        and cached_right.state_id == "pin_alignment_lease"
        and fresh_left.state_id == "bore_clearance_lease"
        and fresh_right.state_id == "pin_alignment_lease"
        and cached_left.active
        and cached_right.active
        and fresh_left.active
        and fresh_right.active
        and cached_left.coordination_generation == cached_right.coordination_generation
        and fresh_left.coordination_generation == fresh_right.coordination_generation
        and cached_left.coordination_generation == fresh_left.coordination_generation
        and cached_right.coordination_generation == fresh_right.coordination_generation
    ):
        await robot.protected_action("insert_aligned_pin", cached_left, cached_right)
