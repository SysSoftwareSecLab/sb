async def consumer_policy(robot, cached_left, cached_right):
    left1 = await robot.observe_authorization("bin_destination_lease")
    right1 = await robot.observe_authorization("parcel_custody_lease")
    left2 = await robot.observe_authorization("bin_destination_lease")
    if left1.coordination_generation != left2.coordination_generation:
        left_final = left2
        right_final = await robot.observe_authorization("parcel_custody_lease")
    else:
        left_final = left2
        right_final = right1
    await robot.protected_action("place_parcel_in_bin", left_final, right_final)
