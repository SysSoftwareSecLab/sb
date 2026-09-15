async def consumer_policy(robot, cached_left, cached_right):
    fresh_left = await robot.observe_authorization("tray_receiver_lease")
    fresh_right = await robot.observe_authorization("tray_custody_lease")
    left_receipt = fresh_left if fresh_left.version > cached_left.version else cached_left
    right_receipt = fresh_right if fresh_right.version > cached_right.version else cached_right
    await robot.protected_action("release_received_tray", left_receipt, right_receipt)
