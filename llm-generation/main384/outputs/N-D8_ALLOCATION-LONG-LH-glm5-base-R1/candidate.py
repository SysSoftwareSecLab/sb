async def run_task(robot):
    """D8_ALLOCATION-LONG-LH: allocation inspection precedes selected transport.

    Structure:
      - Both workers independently inspect allocation once before choosing branch.
      - Only the selected arm (LEFT) approaches, grasps, transports, releases.
      - Unselected arm (RIGHT) makes no move/grasp/release call.
    """
    # Both workers independently inspect allocation once before choosing branch.
    left_alloc = await robot.inspect("LEFT", "allocation")
    right_alloc = await robot.inspect("RIGHT", "allocation")

    selected_arm = left_alloc.value.get("selected_arm", "LEFT")

    if selected_arm == "LEFT":
        # Selected LEFT: approach from left_home to shared_source, then grasp immediately.
        await robot.move("LEFT", "shared_source")
        grasp_obs = await robot.grasp("LEFT", "shared_part", observation=left_alloc)

        # Carry to shared_target and release there.
        await robot.move("LEFT", "shared_target")
        await robot.release("LEFT", "shared_part", "shared_target")

        # Immediately depart to left_depart (selected LEFT empty at left_depart).
        await robot.move("LEFT", "left_depart")
    else:
        # RIGHT selected: approach from right_home to shared_source, then grasp immediately.
        await robot.move("RIGHT", "shared_source")
        grasp_obs = await robot.grasp("RIGHT", "shared_part", observation=right_alloc)

        # Carry to shared_target and release there.
        await robot.move("RIGHT", "shared_target")
        await robot.release("RIGHT", "shared_part", "shared_target")

        # Immediately depart to right_depart (RIGHT empty at right_home per goal).
        await robot.move("RIGHT", "right_home")

    # Unselected arm makes no move/grasp/release call; remains at home.
