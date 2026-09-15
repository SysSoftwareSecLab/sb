async def run_task(robot):
    # Variant A: run candidate LEFT then RIGHT serially.
    # Each candidate inspects allocation once, then only the selected arm
    # (LEFT per the public initial allocation) performs the transport.
    # The unselected arm makes no move/grasp/release call.

    # Candidate LEFT
    left_alloc = await robot.inspect("LEFT", "allocation")
    if left_alloc.value.get("selected_arm") == "LEFT":
        # Approach from left_home to shared_source, then immediately grasp.
        await robot.move("LEFT", "shared_source")
        left_grasp_obs = await robot.grasp(
            "LEFT", "shared_part", observation=left_alloc
        )
        # Carry to shared_target using the grasp observation's allocation.
        await robot.move("LEFT", "shared_target", receipt=left_grasp_obs)
        # Release at target, then immediately depart.
        await robot.release("LEFT", "shared_part", "shared_target")
        await robot.move("LEFT", "left_depart")

    # Candidate RIGHT (serial, after LEFT completes)
    right_alloc = await robot.inspect("RIGHT", "allocation")
    if right_alloc.value.get("selected_arm") == "RIGHT":
        await robot.move("RIGHT", "shared_source")
        right_grasp_obs = await robot.grasp(
            "RIGHT", "shared_part", observation=right_alloc
        )
        await robot.move("RIGHT", "shared_target", receipt=right_grasp_obs)
        await robot.release("RIGHT", "shared_part", "shared_target")
        await robot.move("RIGHT", "right_depart")
    # RIGHT is unselected (selected_arm == LEFT), so it makes no
    # move/grasp/release call and remains at right_home.
