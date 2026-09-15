async def consumer_policy(robot, cached_left, cached_right):
    left1 = await robot.observe_authorization("gear_fixture_lease")
    right1 = await robot.observe_authorization("shaft_alignment_lease")
    left2 = await robot.observe_authorization("gear_fixture_lease")
    if left1.coordination_generation != left2.coordination_generation:
        left_final = left2
        right_final = await robot.observe_authorization("shaft_alignment_lease")
    else:
        left_final = left2
        right_final = right1
    await robot.protected_action("mate_aligned_shaft", left_final, right_final)
