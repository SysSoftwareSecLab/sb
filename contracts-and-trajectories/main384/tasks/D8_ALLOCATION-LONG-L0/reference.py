async def run_task(robot):
    chosen = await robot.inspect("LEFT", "allocation")
    await robot.inspect("RIGHT", "allocation")
    await robot.move("LEFT", "shared_source")
    await robot.grasp("LEFT", "shared_part", observation=chosen)
    await robot.move("LEFT", "shared_target")
    await robot.release("LEFT", "shared_part", "shared_target")
    await robot.move("LEFT", "left_depart")
