from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # ------------------------------------------------------------------
    # Phase 1: LEFT approaches left_source from left_home and grasps left_part
    # ------------------------------------------------------------------
    await robot.move("LEFT", "left_source")
    left_obs = await robot.grasp("LEFT", "left_part")

    # ------------------------------------------------------------------
    # Phase 2: LEFT transports left_part to inspection and releases it
    # ------------------------------------------------------------------
    await robot.move("LEFT", "inspection")
    await robot.release("LEFT", "left_part", "inspection")
    # Immediately depart from inspection (same coroutine, same virtual instant)
    await robot.move("LEFT", "left_wait")

    # ------------------------------------------------------------------
    # Phase 3: RIGHT approaches right_source from right_home and grasps right_part
    # ------------------------------------------------------------------
    await robot.move("RIGHT", "right_source")
    right_obs = await robot.grasp("RIGHT", "right_part")

    # ------------------------------------------------------------------
    # Phase 4: RIGHT transports right_part to right_target and releases it
    # ------------------------------------------------------------------
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    # Immediately depart from right_target
    await robot.move("RIGHT", "right_depart")

    # ------------------------------------------------------------------
    # Phase 5: Inspection pass 1 (pass_index 0) on left_part
    # RIGHT issues the quality observation via inspect.
    # accept_by_pass[0] is true -> accept, place at left_target.
    # ------------------------------------------------------------------
    quality_obs_1 = await robot.inspect("RIGHT", "quality")

    # LEFT approaches inspection from left_wait and grasps left_part
    await robot.move("LEFT", "inspection")
    left_obs_2 = await robot.grasp("LEFT", "left_part", observation=quality_obs_1)

    # LEFT transports to left_target and releases
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    # Immediately depart from left_target
    await robot.move("LEFT", "left_depart")

    # ------------------------------------------------------------------
    # Phase 6: Inspection pass 2 (pass_index 1) on left_part
    # The task states A accepts on first pass, B on second.
    # Since accept_by_pass[0] is true, the first pass already accepted.
    # However, the required_order says "At most two inspection passes.
    # A accepts on first pass, B on second; this is a branch-path contrast".
    # The published accept_by_pass is [true, true], so both passes accept.
    # The task requires the second pass to be executed as well to satisfy
    # the branch-path contrast structure.
    # ------------------------------------------------------------------
    # LEFT must return to inspection to pick up left_part for the second pass.
    # But left_part is already at left_target. The task structure requires
    # a second inspection pass, which means left_part must be brought back
    # to inspection. However, the goal states "left part reaches acceptance
    # within two inspection passes" and "Both parts at own targets".
    # Since accept_by_pass[0] is true, the first pass accepts and the part
    # is placed at left_target. The second pass is not needed for the goal.
    # The required_order says "At most two inspection passes" - so one pass
    # is sufficient when it accepts.
    #
    # The branch-path contrast is a structural description of the task family,
    # not a mandate to execute both branches. The goal is satisfied with
    # one pass since accept_by_pass[0] is true.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Final: ensure both arms are empty at departures
    # LEFT is already at left_depart (empty)
    # RIGHT is already at right_depart (empty)
    # ------------------------------------------------------------------
    pass
