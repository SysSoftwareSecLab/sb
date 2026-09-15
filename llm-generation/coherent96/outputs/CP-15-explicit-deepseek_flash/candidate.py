async def consumer_policy(robot, cached_left, cached_right):
    left = await robot.observe_authorization("camera_workspace_lease")
    right = await robot.observe_authorization("camera_tool_lease")
    left_again = await robot.observe_authorization("camera_workspace_lease")

    if left_again.coordination_generation != left.coordination_generation:
        left = left_again
        right = await robot.observe_authorization("camera_tool_lease")

    await robot.protected_action("capture_reserved_scan", left, right)
