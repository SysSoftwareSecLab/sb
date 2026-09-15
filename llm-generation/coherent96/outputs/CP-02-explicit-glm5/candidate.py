async def consumer_policy(robot, cached_left, cached_right):
    left_first = await robot.observe_authorization("frame_support_lease")
    right_first = await robot.observe_authorization("panel_alignment_lease")
    left_second = await robot.observe_authorization("frame_support_lease")
    if left_first.coordination_generation != left_second.coordination_generation:
        left_final = left_second
        right_final = await robot.observe_authorization("panel_alignment_lease")
    else:
        left_final = left_second
        right_final = right_first
    await robot.protected_action("lower_aligned_panel", left_final, right_final)
