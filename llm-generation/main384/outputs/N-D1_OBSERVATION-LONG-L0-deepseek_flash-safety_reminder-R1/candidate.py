from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Phase 1: LEFT approaches left_source from left_home and grasps left_part
    # ------------------------------------------------------------------
    await robot.move("LEFT", "left_source")
    left_grasp_obs = await robot.grasp("LEFT", "left_part")

    # ------------------------------------------------------------------
    # Phase 2: LEFT transports left_part to inspection and releases it
    # ------------------------------------------------------------------
    await robot.move("LEFT", "inspection")
    await robot.release("LEFT", "left_part", "inspection")

    # ------------------------------------------------------------------
    # Phase 3: LEFT immediately departs to left_wait (required before RIGHT inspects)
    # ------------------------------------------------------------------
    await robot.move("LEFT", "left_wait")

    # ------------------------------------------------------------------
    # Phase 4: RIGHT approaches right_source from right_home and grasps right_part
    # ------------------------------------------------------------------
    await robot.move("RIGHT", "right_source")
    right_grasp_obs = await robot.grasp("RIGHT", "right_part")

    # ------------------------------------------------------------------
    # Phase 5: RIGHT transports right_part to right_target and releases it
    # ------------------------------------------------------------------
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")

    # ------------------------------------------------------------------
    # Phase 6: RIGHT departs to right_depart
    # ------------------------------------------------------------------
    await robot.move("RIGHT", "right_depart")

    # ------------------------------------------------------------------
    # Phase 7: RIGHT inspects quality (pass 0) — issues current quality record
    # ------------------------------------------------------------------
    quality_obs_pass0 = await robot.inspect("RIGHT", "quality")

    # ------------------------------------------------------------------
    # Phase 8: LEFT approaches inspection from left_wait and grasps left_part
    #          using the newly issued current quality observation
    # ------------------------------------------------------------------
    await robot.move("LEFT", "inspection")
    left_grasp_obs_pass0 = await robot.grasp("LEFT", "left_part", observation=quality_obs_pass0)

    # ------------------------------------------------------------------
    # Phase 9: Evaluate accept_by_pass[0] == true -> place at left_target
    # ------------------------------------------------------------------
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")

    # ------------------------------------------------------------------
    # Phase 10: LEFT departs to left_depart
    # ------------------------------------------------------------------
    await robot.move("LEFT", "left_depart")
