async def consumer_policy(robot, cached_left, cached_right):
    left_first = await robot.observe_authorization("press_workspace_lease")
    right_first = await robot.observe_authorization("press_tool_lease")
    left_second = await robot.observe_authorization("press_workspace_lease")
    if left_first.coordination_generation != left_second.coordination_generation:
        left_final = left_second
        right_final = await robot.observe_authorization("press_tool_lease")
    else:
        left_final = left_second
        right_final = right_first
    await robot.protected_action("execute_reserved_press", left_final, right_final)
