async def consumer_policy(robot, cached_left, cached_right):
    left_receipt = await robot.observe_authorization("camera_workspace_lease")
    right_receipt = await robot.observe_authorization("camera_tool_lease")
    if (
        left_receipt.active
        and right_receipt.active
        and left_receipt.coordination_generation == right_receipt.coordination_generation
        and left_receipt.version == right_receipt.version
    ):
        await robot.protected_action("capture_reserved_scan", left_receipt, right_receipt)
