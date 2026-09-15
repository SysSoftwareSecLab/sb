import asyncio
async def run_task(robot):
    async def worker(arm):
        allocation = await robot.inspect(arm, "allocation")
        if allocation.value["selected_arm"] == arm:
            await robot.move(arm, "shared_source")
            await robot.grasp(arm, "shared_part", observation=allocation)
            await robot.move(arm, "shared_target")
            await robot.release(arm, "shared_part", "shared_target")
            await robot.move(arm, arm.lower() + "_depart")
    await asyncio.gather(worker("LEFT"), worker("RIGHT"))
