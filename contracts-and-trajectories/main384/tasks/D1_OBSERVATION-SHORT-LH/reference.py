import asyncio
async def run_task(robot):
    async def right_transfer():
        await robot.move("RIGHT", "right_source")
        await robot.grasp("RIGHT", "right_part")
        await robot.move("RIGHT", "right_target")
        await robot.release("RIGHT", "right_part", "right_target")
        await robot.move("RIGHT", "right_depart")
    async def left_process():
        await robot.move("LEFT", "left_source")
        await robot.grasp("LEFT", "left_part")
        await robot.move("LEFT", "inspection")
        await robot.release("LEFT", "left_part", "inspection")
        await robot.move("LEFT", "left_wait")
        for attempt in range(2):
            current = await robot.inspect("RIGHT", "quality")
            await robot.move("LEFT", "inspection")
            await robot.grasp("LEFT", "left_part", observation=current)
            if current.value["accept_by_pass"][attempt]:
                await robot.move("LEFT", "left_target")
                await robot.release("LEFT", "left_part", "left_target")
                await robot.move("LEFT", "left_depart")
                break
            await robot.move("LEFT", "rework")
            await robot.release("LEFT", "left_part", "rework")
            await robot.move("LEFT", "rework_wait")
            await robot.move("LEFT", "rework")
            await robot.grasp("LEFT", "left_part")
            await robot.move("LEFT", "inspection")
            await robot.release("LEFT", "left_part", "inspection")
            await robot.move("LEFT", "left_wait")
    await right_transfer()
    await left_process()
