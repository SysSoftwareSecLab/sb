async def consumer_policy(robot, cached_left, cached_right):
    left_first = await robot.observe_authorization("receiver_readiness_lease")
    right_first = await robot.observe_authorization("payload_custody_lease")
    left_second = await robot.observe_authorization("receiver_readiness_lease")
    if left_first.coordination_generation != left_second.coordination_generation:
        left_second = await robot.observe_authorization("receiver_readiness_lease")
        right_first = await robot.observe_authorization("payload_custody_lease")
    await robot.protected_action("release_supported_payload", left_second, right_first)
