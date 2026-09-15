import asyncio

async def run_task(robot):
    """
    Executes the CONCURRENT task for layout LH.
    Two independent lanes: LEFT moves left_part, RIGHT moves right_part.
    Sequence: Home -> Source (Approach/Grasp) -> Target (Release) -> Depart.
    """
    
    # Define the sequence for the LEFT arm
    async def run_left():
        # 1. Approach left_source from left_home
        await robot.move("LEFT", "left_home")
        
        # 2. Grasp left_part
        # Approach sequence requires immediate grasp from the same coroutine.
        await robot.grasp("LEFT", "left_part")
        
        # 3. Move to left_target
        await robot.move("LEFT", "left_target")
        
        # 4. Release left_part at left_target
        await robot.release("LEFT", "left_part", "left_target")
        
        # 5. Immediate departure to left_depart
        await robot.move("LEFT", "left_depart")

    # Define the sequence for the RIGHT arm
    async def run_right():
        # 1. Approach right_source from right_home
        await robot.move("RIGHT", "right_home")
        
        # 2. Grasp right_part
        await robot.grasp("RIGHT", "right_part")
        
        # 3. Move to right_target
        await robot.move("RIGHT", "right_target")
        
        # 4. Release right_part at right_target
        await robot.release("RIGHT", "right_part", "right_target")
        
        # 5. Immediate departure to right_depart
        await robot.move("RIGHT", "right_depart")

    # Run both lanes concurrently to satisfy the CONCURRENT structure
    await asyncio.gather(run_left(), run_right())
