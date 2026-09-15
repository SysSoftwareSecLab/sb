async def consumer_policy(robot, cached_left, cached_right):
    left_first = await robot.observe_authorization("carton_support_lease")
    right_first = await robot.observe_authorization("item_custody_lease")
    left_second = await robot.observe_authorization("carton_support_lease")
    if left_first.coordination_generation != left_second.coordination_generation:
        right_second = await robot.observe_authorization("item_custody_lease")
        await robot.protected_action("place_item_in_carton", left_second, right_second)
    else:
        await robot.protected_action("place_item_in_carton", left_second, right_first)
