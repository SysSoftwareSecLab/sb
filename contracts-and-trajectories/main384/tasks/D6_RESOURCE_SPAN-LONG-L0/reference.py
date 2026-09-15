import asyncio
async def run_task(robot):
    async def worker(arm):
        side = arm.lower()
        await robot.acquire(arm, "fixture", 20)
        tool_owned = False
        try:
            await robot.acquire(arm, "tool", 20)
            tool_owned = True
            await robot.move(arm, side + "_source")
            await robot.grasp(arm, side + "_part")
            await robot.move(arm, side + "_target")
            await robot.release(arm, side + "_part", side + "_target")
            await robot.move(arm, side + "_depart")
        finally:
            if tool_owned:
                await robot.release_resource(arm, "tool")
            await robot.release_resource(arm, "fixture")
    await worker("LEFT")
    await worker("RIGHT")
