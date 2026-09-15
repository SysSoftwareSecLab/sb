async def consumer_policy(robot, cached_left, cached_right):
    left1 = await robot.observe_authorization("bin_destination_lease")
    right1 = await robot.observe_authorization("parcel_custody_lease")
    left2 = await robot.observe_authorization("bin_destination_lease")

    if left1.coordination_generation != left2.coordination_generation:
        right2 = await robot.observe_authorization("parcel_custody_lease")
        left = left2
        right = right2
    else:
        left = left2
        right = right1

    if (
        left.active
        and right.active
        and left.coordination_generation == right.coordination_generation
    ):
        await robot.protected_action("place_parcel_in_bin", left, right)
