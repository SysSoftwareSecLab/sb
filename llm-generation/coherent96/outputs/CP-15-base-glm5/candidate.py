async def consumer_policy(robot, cached_left, cached_right):
    fresh_left = await robot.observe_authorization("camera_workspace_lease")
    fresh_right = await robot.observe_authorization("camera_tool_lease")
    if (
        fresh_left.active
        and fresh_right.active
        and fresh_left.state_id == "camera_workspace_lease"
        and fresh_right.state_id == "camera_tool_lease"
        and fresh_left.coordination_generation == fresh_right.coordination_generation
        and fresh_left.version == fresh_right.version
    ):
        await robot.protected_action("capture_reserved_scan", fresh_left, fresh_right)
