
async def run_task(robot):
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
    old = await robot.inspect("LEFT", "route")
    current = await robot.refresh("LEFT", "route")
    selected = old if old.version == current.version else current
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part", observation=selected)
    await robot.move("LEFT", "left_target")
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")
