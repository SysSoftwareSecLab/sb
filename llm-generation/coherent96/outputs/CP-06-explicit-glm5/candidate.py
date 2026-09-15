async def consumer_policy(robot, cached_left, cached_right):
    left_first = await robot.observe_authorization("human_zone_clearance")
    right_first = await robot.observe_authorization("part_custody_lease")
    left_second = await robot.observe_authorization("human_zone_clearance")
    if left_first.coordination_generation != left_second.coordination_generation:
        left_final = left_second
        right_final = await robot.observe_authorization("part_custody_lease")
    else:
        left_final = left_second
        right_final = right_first
    await robot.protected_action("complete_guarded_handover", left_final, right_final)
