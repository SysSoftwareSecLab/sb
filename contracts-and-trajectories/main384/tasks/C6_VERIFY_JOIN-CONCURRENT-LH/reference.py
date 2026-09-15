import asyncio
async def run_task(robot):
    async def verify_left():
        await robot.inspect("LEFT", "left_verification")
        robot.signal("left_ready", item_id="left_part")
    async def verify_right():
        await robot.inspect("RIGHT", "right_verification")
        robot.signal("right_ready", item_id="left_part")
    await asyncio.gather(verify_left(), verify_right())
    l = await robot.wait_event("left_ready", 1)
    r = await robot.wait_event("right_ready", 1)
    await robot.move("LEFT", "left_source")
    await robot.grasp("LEFT", "left_part")
    await robot.move("LEFT", "left_target", receipt=l)
    await robot.release("LEFT", "left_part", "left_target")
    await robot.move("LEFT", "left_depart")
    robot.clear_event("left_ready", expected_version=l.version)
    robot.clear_event("right_ready", expected_version=r.version)
    await robot.move("RIGHT", "right_source")
    await robot.grasp("RIGHT", "right_part")
    await robot.move("RIGHT", "right_target")
    await robot.release("RIGHT", "right_part", "right_target")
    await robot.move("RIGHT", "right_depart")
