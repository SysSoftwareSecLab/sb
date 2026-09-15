async def run_task(robot):
    # LEFT: left_home -> left_source (approach+grasp) -> left_wait -> inspection (grasp) -> left_target (release) -> left_depart
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_wait")
    await robot.move("LEFT", "inspection")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")

    # RIGHT: right_home -> right_source (approach+grasp) -> right_target (release) -> right_depart
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
